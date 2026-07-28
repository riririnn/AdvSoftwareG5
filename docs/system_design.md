# 無人販売所システム 設計書

結合テスト（2026-07-14〜16）で実機検証した結果・制約を反映した設計書。
「なぜこの設計なのか」を、実際に起きた障害と対策に基づいて記録する。

---

## 1. 全体アーキテクチャ

```
【ラズパイ aseg1 (Raspberry Pi 3 B+)】
  ├ 監視カメラ (video0, USB)  ──┐
  ├ コイン・野菜カメラ (video2) ─┼─ controller.py（セッション制御）
  ├ HX711ロードセル×2 (GPIO)  ──┘        │
  │                                       │ JPEG画像をHTTP POST
  │                              Tailscale│(100.98.67.33:8080/predict)
  │                                       ▼
【GPUサーバー rin-office (Ubuntu + RTX 5060 Ti, DevContainer内)】
  │  web_server.py ─ YOLOv8m(野菜・硬貨56クラス) + YOLOv8s(person)
  │       │ 検出結果JSON
  │       ▼
  └ controller.py が coin.csv / vegetable.csv / weight.csv / 録画 を
    sessions/<日時>/ に保存 → theft_checker.py(万引き判定) → session.json
         │
         ▼
  Flask/app.py が sessions/ を監視して自動取込 → 在庫・売上・LINE通知
```

### 設計原則

- **ラズパイは薄いクライアント**: 撮影・センサー・制御のみ。AI推論はGPUサーバー
- **モジュール間はファイル(CSV/JSON)とHTTP(JSON)で疎結合**
- **接続はTailscale経由**: 別ネットワークでも動く。`localhost`や`192.168.x.x`は使わない

---

## 2. プロセス・スレッド構成（ラズパイ側）

```
controller.py プロセス（sudo で起動）
├ メインスレッド: セッション制御ループ
│    人待ち → セッション開始 → (録画+コイン認識+人検知)ループ → 判定起動
├ _FrameGrabber スレッド (video0): 監視カメラを常時読み取り
├ _FrameGrabber スレッド (video2): コイン・野菜カメラを常時読み取り
│    ※ コインと野菜は同一カメラのため1スレッドを自動共有
└ (セッション終了時) theft_checker.py をサブプロセスで起動
```

### なぜカメラは専用スレッドで常時読むのか

メインループはサーバーへの推論リクエストで0.5〜1.3秒待つ。read()の呼び出しを
メインループに置くと読み取り間隔が空き、ドライバの内部状態が乱れる。
専用スレッドが途切れず読み続け、メインは「最新フレーム」を取るだけにする。

---

## 3. ハードウェア制約と設計判断（実機で検証済みの教訓）

### 3-1. USB帯域: カメラは必ずMJPGモードで開く【最重要】

- UVCカメラの既定は**無圧縮YUYV**: 640x480@30fpsで**1台約18MB/s**
- **Pi 3は全USBポート＋有線LANが1本のUSB2.0バス（実効〜35MB/s）を共有**
- カメラ2台をYUYVで同時使用 → 帯域飽和 → **約10秒周期の select() timeout**
  が発生することを実機で確認（1台のみなら60秒間エラーゼロ）
- 対策: `cv2.CAP_PROP_FOURCC = MJPG` + `CAP_PROP_FPS = 10` を必ず設定
  （controller.py の `_open_camera()` に実装済み。解像度設定より先にFOURCC）

### 3-2. HX711（重量センサー）: 読み取り中だけSCHED_FIFO

- HX711はSCKパルスを**60マイクロ秒以内**に収める必要がある
- 通常優先度のPythonでは、OSの割り込みでこの制約を**ほぼ100%超過**し
  読み取りが全滅することを実機で確認 → root+SCHED_FIFO化で解決
- ただし常時SCHED_FIFOだと他スレッド（カメラ等）を圧迫するため、
  **`get_weights()`の計測区間だけ昇格**するコンテキストマネージャ方式
  （raspberry_pi.py の `_realtime_priority` に実装済み）
- このため **controller.py は `sudo python3 controller.py` で起動する**
- PyPIの`hx711`は複数の実装が存在する。実機の版(1.1.2.3)は
  `get_raw_data()`のみでゼロ点/グラム換算は自前実装。さらに同関数は
  失敗時に**無限ループ**する欠陥があるため、有限リトライでラップしている

### 3-3. SDカード: I/O異常の症状と対処

- 実機で `git`コマンド自体が `Input/output error` になる事象が発生
  （原因: SDカードの接触不良。抜き差しで解消）
- 症状: あらゆるコマンドがI/Oエラー / Pythonが標準ライブラリを読めない
- 対処: 書き込みを続けず再起動 → 再発するならSDカード交換を検討

### 3-4. カメラのデバイス番号

- USBカメラ1台は `/dev/video*` を**2つ占有**し、撮影できるのは若い方のみ
- `bcm2835-*` 系(video10〜31)はPi内蔵の処理ブロックでカメラではない
- 確認: `v4l2-ctl --list-devices`
- 現在の割り当て: 監視=video0（UVC Camera）/ コイン・野菜=video2（C922）
  → `app/config.py` の `*_CAMERA_INDEX`

### 3-5. 終了処理

- Ctrl+C時に必ずカメラとGPIOを解放する（`main()`のtry/finally）。
  解放しないと次回起動時に `can't open camera by index` になることがある

---

## 4. サーバー側の設計

- モデル2つを起動時に1回ロード:
  - 野菜・硬貨: `ai/runs/vegetables_v1/weights/best.pt`（自前学習、Git同梱）
  - 人間: `ai/weights/yolov8s.pt`（COCO事前学習済み、**Git同梱**）
    ※ 同梱しないとオフラインのコンテナで起動時に自動DLを試みて
    `Temporary failure in name resolution` でクラッシュする（実機で発生）
- DevContainer内で動かす場合、`runArgs` の `-p 8080:8080`（設定済み）を
  反映したコンテナであること。未反映ならホストで socat 中継:
  `socat TCP-LISTEN:8080,fork,reuseaddr TCP:<コンテナIP>:8080 &`
  （`forwardPorts` はVSCode専用転送でLAN/Tailscaleからは届かない）

---

## 5. 設定パラメータ一覧（app/config.py）

| パラメータ | 現在値 | 変更してよい範囲・注意 |
|-----------|--------|----------------------|
| PREDICT_SERVER_URL | http://100.98.67.33:8080 | サーバーのTailscale IP。テスト環境ごとに変更 |
| MONITOR_CAMERA_INDEX | 0 | `v4l2-ctl --list-devices` の実機値に合わせる |
| COIN/VEGETABLE_CAMERA_INDEX | 2 | 同上。同値なら1カメラを自動共有 |
| CAMERA_FPS | 10 | 上げるとUSB帯域を圧迫（3-1参照） |
| COIN_DETECT_INTERVAL | 0.5秒 | 短くしすぎると推論が詰まる。0.2〜0.5が目安 |
| PERSON_DISAPPEAR_TIME | 3.0秒 | 退店判定。誤検知が多い場合は伸ばす |
| PERSON/COIN/VEGETABLE_CONF_THRESHOLD | 0.5/0.5/0.4 | 誤検出が多ければ上げる |
| (raspberry_pi.py) COIN_SCALE_RATIO / VEGE_SCALE_RATIO / TARE_VEGE_PLATFORM | 1880/1000/148.0 | **実測校正済みの値に要更新**（分銅・実測で調整） |

---

## 6. 既知の障害モードと対処表（実際に起きたもの）

| 症状 | 原因 | 対処 |
|------|------|------|
| video0が約10秒周期でselect() timeout | カメラ2台のYUYV同時使用によるUSB帯域飽和 | MJPG+FPS制限（実装済み）。再発時はFPSをさらに下げる |
| HX711読み取りが全サンプル失敗 | 60µs制約をPythonが超過 | sudoで起動（計測時のみSCHED_FIFO、実装済み） |
| raspberry_pi.pyが無反応でフリーズ | hx711ライブラリのget_raw_data無限ループ | 有限リトライ実装済み。頻発時は配線・電源も確認 |
| 全コマンドがInput/output error | SDカード接触不良/劣化 | 書き込みをやめて再起動。再発ならSD交換 |
| can't open camera by index | 前回プロセスの残留/未解放 | `sudo pkill -f python3` → 再実行（終了処理は実装済み） |
| サーバー起動時にname resolutionエラー | オフラインでyolov8s.ptをDL試行 | モデルGit同梱済み。pull漏れがないか確認 |
| ラズパイからConnection refused | サーバー未起動/ポート未公開/localhost指定 | 手順書(raspi_connection_guide.md)の順に確認 |
| 重量が常に0.0g | スケール係数・風袋が未校正 | 5章の校正パラメータを実測で調整 |
| ダミー値で動作します(sudo時) | rootにRPi.GPIO/hx711が未インストール | `sudo pip3 install RPi.GPIO hx711 --break-system-packages` |

---

## 7. 未解決事項・今後の課題

- [ ] 重量センサーのスケール校正値の確定（分銅による実測）
- [ ] 実環境（販売台・実照明）での認識精度の測定と、必要なら追加学習
- [ ] LINE通知トークンの設定（Web UI担当）
- [ ] 録画fpsと実際の書き込みレートの不一致（動画の再生速度が実時間とずれる）
- [ ] SDカードの信頼性（劣化の兆候があれば交換）

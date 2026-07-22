# 結合テスト 実行手順（最初から最後まで）

この手順書は、サーバー起動からラズパイでの本番シナリオ実行、管理画面での確認までを
一気通貫で行うための完全版である。誰が実施しても同じ手順・同じ結果になるよう、
コマンドはすべてコピペ可能な完成形で記載する。

## この構成の実機情報

| 役割 | マシン | Tailscale IP |
|------|--------|-------------|
| 推論サーバー | rin-office（Ubuntu, GPU, DevContainer内） | **100.98.67.33** |
| ラズパイ | aseg1（Raspberry Pi 3 B+） | 100.120.189.9 |

- 作業ブランチ: **`integration-test`**（サーバー・ラズパイ両方）
- 接続は **Tailscale経由**（`localhost` や `192.168.x.x` は使わない）
- カメラ構成（`app/config.py`）: 監視=`video0`（UVC Camera 046d:081b, C310）/
  コイン・野菜=`video2`（C922 Pro Stream Webcam, 共用）
- 設計の背景・制約・障害対処の一覧は `docs/system_design.md` を参照
- カメラのCorrupt JPEG問題の詳細な診断記録は `docs/corrupt_jpeg_diagnosis.md` を参照

## 現在の状態（2026-07-16時点）

以下は解決済み。カメラ・録画・判定ロジックまわりは実機で安定動作を確認している。

- ✅ カメラ2台同時使用時の `select() timeout`（MJPG化で解消）
- ✅ video0の `Corrupt JPEG data` 警告（video0のみYUYVに切替、`NO_MJPG_CAMERA_INDEXES`で解消）
- ✅ `monitor.mp4` の録画時間が実時間とズレる問題（録画専用スレッド化で解消）
- ✅ 野菜が全部持ち去られた（after検出0件）とERROR判定になる問題（マーカー行方式で解消）
- ✅ 判定根拠として `vegetable_before.jpg` / `vegetable_after.jpg`（検出枠つき）を自動保存

未解決・既知の注意点:

- ⚠️ video0のUSB接続が物理的に不安定になることがある（`dmesg`に
  `device descriptor read/64, error -32` 等が出て一時的に `can't open camera by index`
  になる）。コード側で再接続リトライはしているが、頻発する場合はケーブル・
  コネクタの接触を物理的に確認する
- ⚠️ 重量センサー（コイン用）が0.0のままだったことがあった。硬貨がロードセルの
  上に正しく乗っているか物理配置を確認する（別セッションでは正常値143.9gを記録済み）

---

## 1. サーバー起動（🖥️ コンテナ内）

```bash
cd /workspace
tmux attach -t server   # 前回のセッションが残っていればこれで復帰
# セッションが無ければ:
tmux new -s server
python app/web_server.py
```

`Starting minimal web server on port 8080...` が出れば成功。`Ctrl+b` → `d` でデタッチ。

## 2. socat中継の起動（🖥️ Ubuntu本体 `rin@rin-office`）

前回のターミナルを閉じていれば中継は止まっているので、再度張る。
まず🖥️コンテナ内で `hostname -I` を実行してコンテナのIPを確認し（例: 172.17.0.2）、
**山括弧なしで**そのIPを指定する:

```bash
socat TCP-LISTEN:8080,fork,reuseaddr TCP:172.17.0.2:8080 &
```

確認:

```bash
curl http://localhost:8080/status   # → {"sales_count": 0, ...} が返ればOK
```

⚠️ **このターミナルは閉じない。** 閉じると中継が止まりラズパイから繋がらなくなる。

## 3. ラズパイを最新化して疎通確認（🍓 ラズパイ）

ラズパイの `app/config.py` には `PREDICT_SERVER_URL` をTailscale IPに書き換えた
ローカル変更が残っているため、`git pull` の前に必ず退避する。

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
git stash
git pull
git stash pop
```

`stash pop` 後に `app/config.py` の差分を確認し、`PREDICT_SERVER_URL` が
`http://100.98.67.33:8080` になっていることを確認する:

```bash
git diff config.py    # app/ディレクトリの中にいる場合。リポジトリルートなら app/config.py
```

疎通確認:

```bash
curl http://100.98.67.33:8080/status
```

## 4. カメラ動作確認（🍓 ラズパイ、任意・トラブル時の切り分け用）

普段はスキップしてよい。`select() timeout` や `Corrupt JPEG` が疑われる場合のみ、
本体コードに依存しない診断専用スクリプトで確認する:

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
python3 scripts/camera_diagnosis.py --cameras 0 2 --fps 10 --no-mjpg-cameras 0 2> /tmp/stderr.log
grep -c "Corrupt JPEG" /tmp/stderr.log
```

- **警告0件・両カメラとも550フレーム以上・read失敗0** → 正常。手順5へ進む
- 異常が出た場合は `docs/corrupt_jpeg_diagnosis.md` の診断手順に従う

## 5. controller起動と本番シナリオ（🍓 ラズパイ）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
sudo python3 controller.py
```

※ `sudo`のみでよい（`chrt`や環境変数は不要。重量読み取りの瞬間だけ
自動でリアルタイム優先度に切り替わる）。

### 動作シナリオ

1. **監視カメラ（video0）の前に立つ** → `Customer detected.` → `Session started.`
2. **野菜カメラ（video2）に野菜を置く**（入店時の在庫として記録される）
3. **コイン・野菜カメラ（video2）に硬貨を置く**（1枚ずつ、重ねない。100円玉が高精度）
4. 万引きを試す場合は、セッション中に野菜を取り去る（重量センサーの上から動かす）
5. **監視カメラの前から離れて3秒待つ** → `Customer left.` → 万引き判定結果が表示

### 成功条件

- [ ] `select() timeout` が出ない（60秒以上）
- [ ] `Corrupt JPEG` が大量に出ない
- [ ] coin.csv に投入した硬貨が記録される
- [ ] vegetable.csv に before/after 両方が記録される（全部持ち去った場合は
      after側が `(none),0` のマーカー行になる。これはERRORではなく正常）
- [ ] session.json に `"judgement": "normal"` または `"theft"` が入る
- [ ] monitor.mp4 の再生時間がセッションの実時間とほぼ一致する

### 結果確認

```bash
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/coin.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/weight.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/session.json
```

判定根拠画像（検出枠つき）も確認できる:

```bash
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable_*.jpg
```

PCで動画・画像を目視したい場合は、PC側のターミナルでTailscale経由でscpする:

```bash
scp aseg1@100.120.189.9:~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/monitor.mp4 ./
scp "aseg1@100.120.189.9:~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable_*.jpg" .
```

## 6. 管理画面（web_admin）での確認（🍓 ラズパイ）

旧 `Flask/` ディレクトリは廃止され、現在は `app/web_admin/` に移行済み。
`sessions/` フォルダを自動監視し、セッション完了時に在庫更新・売上/通知履歴への
反映・LINE通知送信までを自動で行う。

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
python3 -m web_admin.web_app
```

起動時に `sessions/` 内の既存セッションから履歴を復元し
（`sync_web_histories_from_sessions`）、その後5秒間隔でバックグラウンド監視を
開始する（`WATCH_INTERVAL_SEC` 環境変数で変更可）。

ターミナルを開いたままにしたくない場合は `tmux` を使うと便利
（無くても動作には影響しない。単にターミナルを閉じるとプロセスも終わるだけ）:

```bash
sudo apt update && sudo apt install -y tmux   # 未インストールの場合のみ
tmux new -s webadmin
cd ~/advance_software_engnering/AdvSoftwareG5/app
python3 -m web_admin.web_app
# Ctrl+b → d でデタッチ
```

PCのブラウザで開く:

```
http://100.120.189.9:5000
```

### 確認すること

- [ ] 直近のセッションの判定結果（購入/万引き）が売上履歴・通知履歴に反映されている
- [ ] `normal`判定のセッションで在庫数が減少している
- [ ] LINE通知が送信される設定であれば、通知が届いている

---

## 中断する場合

```bash
Ctrl+C   # controller は終了処理（録画スレッド停止・カメラ・GPIO解放）が自動で走る
```

作業内容はすべて `integration-test` ブランチにpush済みなので何も失われない。
次回は本手順書の「1. サーバー起動」から再開すればよい。

## トラブル時

- カメラ関連（`Corrupt JPEG` / `select() timeout` / `can't open camera by index`）
  → `docs/corrupt_jpeg_diagnosis.md` の診断手順、および本書「現在の状態」の
    既知の注意点を参照
- その他の障害モードと対処表 → `docs/system_design.md` の
  「6. 既知の障害モードと対処表」を参照

# 結合テスト 再開手順

完了済み：サーバー起動・ポート公開・疎通確認・静止画推論・カメラ2台特定・
重量センサー動作確認（コイン/野菜とも計測成功）・
カメラタイムアウト対策（MJPG化）・Corrupt JPEG対策（video0のみYUYV化、
経緯は `docs/corrupt_jpeg_diagnosis.md`）・録画時間ズレ修正（録画スレッド化）。
いずれも実機検証済み。

**現在地: 残りは (1) 野菜を実際に置いた本番シナリオ1周の完走
（これまでのERROR判定は野菜未設置によるもので正常動作）、
(2) weight.csv が0.0のままになる件の調査（コイン3枚投入でもcoinbox重量が
0.0だった。センサー単体テスト `sudo python3 app/raspberry_pi.py` で切り分け）、
(3) Flask管理画面の確認（任意）。**

設計の背景・制約・障害対処の一覧は `docs/system_design.md` を参照。

## この構成の実機情報

| 役割 | マシン | Tailscale IP |
|------|--------|-------------|
| 推論サーバー | rin-office（Ubuntu, GPU, DevContainer内） | **100.98.67.33** |
| ラズパイ | aseg1（Raspberry Pi 3 B+） | 100.120.189.9 |

- 作業ブランチ: **`integration-test`**（サーバー・ラズパイ両方）
- 接続は **Tailscale経由**（`localhost` や `192.168.x.x` は使わない）
- カメラ設定（`app/config.py`）: 監視=`video0` / コイン・野菜=`video2`

---

## 1. サーバー再起動（🖥️ コンテナ内）

```bash
cd /workspace
tmux attach -t server   # 前回のセッションが残っていればこれで復帰
# セッションが無ければ:
tmux new -s server
python app/web_server.py
```

`Starting minimal web server on port 8080...` が出れば成功。`Ctrl+b` → `d` でデタッチ。

## 2. socat中継の再起動（🖥️ Ubuntu本体 `rin@rin-office`）

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

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
git pull
curl http://100.98.67.33:8080/status
```

---

## 4. カメラ2台同時テスト（🍓 ラズパイ、本番構成の事前確認・任意）

controller起動前にカメラ疎通を確認したい場合は、本番と同じ
「video0=YUYV + video2=MJPG」構成の診断スクリプトを使う:

```bash
python3 scripts/camera_diagnosis.py --cameras 0 2 --fps 10 --no-mjpg-cameras 0 2> /tmp/stderr.log
grep -c "Corrupt JPEG" /tmp/stderr.log
```

- **両方とも read失敗0・警告0** → 手順5へ（2026-07-16に確認済みの状態）
- **失敗や警告が出る** → 結果を報告する。`docs/corrupt_jpeg_diagnosis.md` の
  手順・記録表で再診断する

## 5. controller起動と本番シナリオ（🍓 ラズパイ）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
sudo python3 controller.py
```

※ `sudo`のみでよい（`chrt`や環境変数は不要になった。重量読み取りの
瞬間だけ自動でリアルタイム優先度に切り替わる）。

### 動作シナリオ

1. **監視カメラ（video0）の前に立つ** → `Customer detected.` → `Session started.`
2. **コイン・野菜カメラ（video2）に硬貨を置く**（1枚ずつ、重ねない。100円玉が高精度）
3. **監視カメラの前から離れて3秒待つ** → `Customer left.` → 万引き判定結果が表示

### 成功条件

- [ ] `select() timeout` が出ない（60秒以上）
- [ ] coin.csv に投入した硬貨が記録される
- [ ] vegetable.csv に before/after 両方が記録される（判定がERRORにならない）
- [ ] session.json に `"judgement": "normal"` または `"theft"` が入る

### 結果確認

```bash
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/coin.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/session.json
```

---

## 6. Flask管理画面（🍓 ラズパイ、任意）

```bash
tmux new -s flask
cd ~/advance_software_engnering/AdvSoftwareG5/Flask
python3 app.py
```

PCのブラウザで `http://<ラズパイのIP>:5000` を開くと管理画面。
セッション完了の数秒後に売上・通知が自動反映される。

---

## 中断する場合

```bash
Ctrl+C   # controller は終了処理（カメラ・GPIO解放）が自動で走る
```

作業内容はすべて `integration-test` ブランチにpush済みなので何も失われない。
次回は本手順書の「1. サーバー再起動」から再開すればよい。

## トラブル時

`docs/system_design.md` の「6. 既知の障害モードと対処表」を参照
（今回の結合テストで実際に起きた事象と対処の一覧）。

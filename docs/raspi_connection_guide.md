# ラズパイ接続・カメラ認識 完全手順書（実機検証済み）

推論サーバー（Ubuntu + GPU）とRaspberry Piを Tailscale で接続し、カメラ認識を
動かすまでの全手順。2026-07-14 の結合テストで実際にたどった手順・つまずき所を反映。

## この構成の実機情報

| 役割 | マシン | Tailscale IP | 備考 |
|------|--------|-------------|------|
| 推論サーバー | rin-office（Ubuntu, GPU） | **100.98.67.33** | DevContainer内でサーバーを起動 |
| ラズパイ | aseg1（Raspberry Pi OS） | 100.120.189.9 | カメラ2台・重量センサー接続 |

- 作業ブランチは **`integration-test`**（サーバー・ラズパイ両方）
- サーバーとラズパイは別ネットワークでも **Tailscale経由**で接続する
  （同一LANの `192.168.x.x` は今回は使わなかった）

---

## パート1: サーバー側（Ubuntu / DevContainer）

### 1-1. ブランチを合わせる（🖥️ コンテナ内）

```bash
cd /workspace
git fetch origin
git switch integration-test
git pull
```

### 1-2. 同梱モデルの確認（🖥️ コンテナ内）

```bash
ls -la ai/runs/vegetables_v1/weights/best.pt   # 野菜・硬貨モデル（約50MB）
ls -la ai/weights/yolov8s.pt                    # 人間検出モデル（約22MB）
```

⚠️ **両方リポジトリに同梱済み。** これがないとサーバー起動時に人間検出モデルを
ネットからダウンロードしようとし、オフライン環境では
`Temporary failure in name resolution` で**起動に失敗する**（実際に発生した）。

### 1-3. サーバー起動（🖥️ コンテナ内、必ずtmux内で）

```bash
tmux new -s server
python app/web_server.py
```

`Starting minimal web server on port 8080...` が出れば成功。
`Ctrl+b` → `d` でデタッチ（サーバーは動いたまま）。

### 1-4. サーバー自身で生存確認（🖥️ コンテナ内）

コンテナには `curl` が無いので Python で確認:

```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/status').read())"
```

`{"sales_count": 0, ...}` が返ればサーバーは生きている。

---

## パート2: コンテナのポートをホストに公開する（重要）

DevContainer内のサーバーは、そのままでは**ホストの外（ラズパイ）から見えない**。
コンテナは隔離ネットワークで、ホスト:8080 に来た通信は自動ではコンテナに入らない。

```
ラズパイ ──Tailscale──▶ ホスト:8080 ──?──▶ コンテナ:8080（サーバー）
                                      ↑ここに通路が必要
```

### 方法A: socat中継（今回採用・リビルド不要）

**🖥️ Ubuntu本体（`rin@rin-office`、コンテナの外）**で実行:

```bash
# コンテナのIPを確認（コンテナ内で hostname -I → 例 172.17.0.2）
sudo apt install -y socat
socat TCP-LISTEN:8080,fork,reuseaddr TCP:172.17.0.2:8080 &
```

⚠️ **socatはホストで動かす。** コンテナ内で動かしても通信がホストから
コンテナに入ってこないため無意味。`sudo` は apt install に必要なだけ。
**このターミナルは閉じない**（閉じると中継が止まる）。

確認（🖥️ Ubuntu本体）:

```bash
curl http://localhost:8080/status   # → {"sales_count": 0, ...} が返ればOK
```

### 方法B: `-p 8080:8080` でリビルド（恒久対応・後日用）

`devcontainer.json` の `runArgs` に `"-p", "8080:8080"` は設定済み。
`Ctrl+Shift+P` → `Dev Containers: Rebuild Container` でリビルドすれば
socat不要になる（ただしリビルド中はセッションが切れサーバー再起動が必要）。
`forwardPorts` はVSCode経由の転送のみでLAN/Tailscaleの他機器からは届かないため、
`-p` が必須。

---

## パート3: ラズパイ側のセットアップ

### 3-1. ブランチを合わせる（🍓 ラズパイ）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
git fetch origin
git switch integration-test
git pull
```

### 3-2. 必要ライブラリのインストール（🍓 ラズパイ）

Raspberry Pi OS は PEP668 で pip が制限されるため apt を使う:

```bash
sudo apt update
sudo apt install -y python3-opencv v4l-utils
pip3 install hx711 --break-system-packages   # 重量センサー用（aptに無いため）
```

※ `RPi.GPIO` は最初から入っていることが多い（`python3 -c "import RPi.GPIO"` で確認）。
※ 推論はサーバーで行うので、ラズパイに ultralytics / PyTorch は**不要**。
　OpenCVはカメラ撮影・JPEG圧縮・録画のためだけに使う。

### 3-3. サーバーIPを設定（🍓 ラズパイ）

```bash
nano app/config.py
```

`Ctrl+W` → `PREDICT` で該当行へジャンプし、サーバーのTailscale IPに変更:

```python
PREDICT_SERVER_URL = "http://100.98.67.33:8080"
```

`Ctrl+O` → `Enter` → `Ctrl+X` で保存。

### 3-4. 疎通確認（🍓 ラズパイ）

```bash
curl http://100.98.67.33:8080/status
```

`{"sales_count": 0, ...}` が返れば接続成功。

⚠️ **`localhost` を使わないこと。** ラズパイで `localhost` はラズパイ自身を指すので
繋がらない。必ずサーバーのTailscale IP（`100.98.67.33`）を指定する。

### 3-5. 静止画で推論経路テスト（🍓 ラズパイ）

```bash
python3 app/simulate_raspi.py --image unattended_sales_place_images/selfsellingstation.jpg --server http://100.98.67.33:8080
```

`carrot conf=...` のような検出結果が出れば、ラズパイ→サーバー→JSONの全経路が動作。

---

## パート4: カメラの確認と設定

### 4-1. カメラの特定（🍓 ラズパイ）

```bash
v4l2-ctl --list-devices
```

⚠️ **`/dev/video*` は大量に出るが大半はカメラではない。**
`bcm2835-codec` / `bcm2835-isp` はラズパイ内蔵の映像処理ブロック（video10〜31）。
**USBカメラは若い番号（0〜3）**に割り当てられる。

さらに **USBカメラ1台につき2つの番号を占有し、撮影できるのは偶数番（若い方）のみ。**
実際に撮れるかは以下で確認:

```bash
python3 -c "
import cv2
for i in [0, 1, 2, 3]:
    cap = cv2.VideoCapture(i)
    ok, _ = cap.read()
    print(f'video{i}:', 'OK' if ok else 'NG')
    cap.release()
"
```

### 4-2. 今回の結合テスト機の実際の割り当て

```
UVC Camera (046d:081b)      → /dev/video0  ✅撮影OK   → 監視カメラ
C922 Pro Stream Webcam      → /dev/video2  ✅撮影OK   → コイン・野菜カメラ
（video1, video3 はメタデータ用でNG）
```

→ `app/config.py` は **監視=0 / コイン・野菜=2** に設定済み:

```python
MONITOR_CAMERA_INDEX = 0
COIN_CAMERA_INDEX = 2
VEGETABLE_CAMERA_INDEX = 2
```

カメラの接続位置が変わって番号が変わったら、この値を実機に合わせて修正する。

---

## パート5: 重量センサーの確認（🍓 ラズパイ）

```bash
cd app
python3 raspberry_pi.py
```

- `ゼロ点調整が完了しました` → 実測値が0.5秒ごとに表示されればOK。`Ctrl+C`で終了
- `ダミー値で動作します` → センサー未接続 or ライブラリ不足（ダミーでもテストは続行可）
- 野菜台の風袋 `TARE_VEGE_PLATFORM = 148.0`（g）は台だけ乗せた実測値に要調整

---

## パート6: 本番起動（controller）

### 6-1. controller起動（🍓 ラズパイ）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
tmux new -s controller
python3 controller.py
```

`[Controller] AIモードで起動します（推論サーバー: http://100.98.67.33:8080）` と出て
人待ちになる。

### 6-2. 動作シナリオ

1. **監視カメラ（video0）の前に立つ** → `Customer detected.` → `Session started.`
2. **コイン・野菜カメラ（video2）に硬貨を置く**（1枚ずつ、重ねない。100円玉が高精度）
3. **監視カメラの前から離れて3秒待つ** → `Customer left.` → 万引き判定結果が表示

### 6-3. 結果確認（🍓 ラズパイ）

```bash
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/coin.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/session.json
```

---

## パート7: Flask管理画面（🍓 ラズパイ、任意）

```bash
tmux new -s flask
cd ~/advance_software_engnering/AdvSoftwareG5/Flask
pip3 install flask --break-system-packages
python3 app.py
```

PCのブラウザで `http://<ラズパイのIP>:5000` を開くと管理画面。
セッション完了の数秒後に売上・通知が自動反映される。

---

## つまずき所まとめ（今回実際に起きた順）

| 症状 | 原因 | 解決 |
|------|------|------|
| サーバーが起動時にクラッシュ | yolov8s.pt をオフラインでDL試行 | モデルをリポジトリに同梱（対応済み） |
| ラズパイで `No route to host` | LAN(192.168系)で別ネットワーク | Tailscale IP(100.x)を使う |
| ラズパイで `Could not connect` | ①サーバー未起動 ②`localhost`を指定 | サーバー起動＋TailscaleIPを指定 |
| ホストから8080に繋がらない | コンテナのポートが未公開 | ホストで socat 中継（パート2） |
| `pip install` が `externally-managed` | Raspberry Pi OSのPEP668制限 | `apt install python3-xxx` か `--break-system-packages` |
| `/dev/video*` が大量 | ラズパイ内蔵処理ブロック | USBカメラは偶数番の若い番号のみ |

## よく使うコマンド早見表

| やりたいこと | 端末 | コマンド |
|-------------|------|---------|
| サーバー画面に戻る | 🖥️コンテナ | `tmux attach -t server` |
| tmuxから抜ける | 共通 | `Ctrl+b` → `d` |
| サーバー生存確認（curl無し） | 🖥️コンテナ | `python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/status').read())"` |
| socat中継（ホスト） | 🖥️本体 | `socat TCP-LISTEN:8080,fork,reuseaddr TCP:172.17.0.2:8080 &` |
| ラズパイから疎通 | 🍓ラズパイ | `curl http://100.98.67.33:8080/status` |
| 静止画テスト | 🍓ラズパイ | `python3 app/simulate_raspi.py --image <画像> --server http://100.98.67.33:8080` |
| カメラ一覧 | 🍓ラズパイ | `v4l2-ctl --list-devices` |
| 重量センサー確認 | 🍓ラズパイ | `cd app && python3 raspberry_pi.py` |

# ラズパイ接続・カメラ認識 完全手順書

推論サーバー（Ubuntu + GPU）とRaspberry Piを接続し、カメラ認識を動かすまでの
全手順を省略なしで記述する。上から順に実行すれば動く状態になることを目指す。

## 前提条件

- Ubuntu側: 推論サーバーを立てるマシン（GPU搭載、リポジトリclone済み、学習済みモデルあり）
- ラズパイ側: Raspberry Pi（OS起動済み、ネットワーク接続済み、SSHまたは直接操作可能）
- 両方が**同じネットワーク**（同じWi-Fiルーター/LAN）に接続されていること
- USBカメラ2台（監視用・コイン野菜用）

---

## パート1: Ubuntu側（推論サーバー）

### 1-1. ターミナルを開き、リポジトリへ移動

```bash
cd ~/AdvSoftwereG5
```

※ パスは自分の環境のリポジトリの場所に読み替える。場所がわからない場合:
`find ~ -maxdepth 3 -name "AdvSoftwereG5" -type d 2>/dev/null`

### 1-2. 最新のコードを取得

```bash
git pull
```

`Already up to date.` または更新ログが出ればOK。

### 1-3. 学習済みモデルの存在確認

```bash
ls -la ai/runs/vegetables_v1/weights/best.pt
```

ファイルが表示されればOK（約50MB）。
`No such file` の場合は `git pull` で取得されるはず（Git管理済みのため）。

### 1-4. tmuxセッションを作ってサーバーを起動

⚠️ **DevContainer内でサーバーを動かす場合**は、`devcontainer.json` に
`"-p", "8080:8080"` が入った状態でコンテナをビルドしていることが前提
（設定済み。ただし**設定追加前に作られたコンテナはリビルドが必要**：
VSCodeで `Ctrl+Shift+P` → `Dev Containers: Rebuild Container`）。
これがないとコンテナ内のサーバーにラズパイから接続できない。

SSH切断や誤操作でサーバーが落ちないよう、必ずtmux内で起動する。

```bash
tmux new -s server
```

画面が切り替わったら（下部に緑のバーが出る）:

```bash
python app/web_server.py
```

### 1-5. 起動完了を待つ

以下が表示されるまで**数十秒待つ**（モデルロードに時間がかかる）:

```
Starting minimal web server on port 8080...
```

※ 初回起動時は人間検出用モデル `yolov8s.pt` の自動ダウンロードが入り、さらに時間がかかる。

### 1-6. tmuxからデタッチ（サーバーは動いたまま抜ける）

キーボードで **`Ctrl+b` を押して離し、続けて `d`** を押す。
元の画面に戻るが、サーバーは裏で動き続けている。

※ サーバーの画面に戻りたいとき: `tmux attach -t server`

### 1-7. サーバーのIPアドレスを確認

⚠️ **必ずUbuntu本体のターミナルで実行すること。**
プロンプトが `root@033905ed6aa6:/workspace#` のような英数字の羅列になっている場合は
**DevContainerの中**にいる。その状態で調べると `172.17.0.2` のような
**コンテナ内部のIP**が出てしまい、ラズパイからは接続できない。
プロンプトが `rin@rin-office:~$` のようにUbuntuのユーザー名になっている
ターミナル（VSCodeの外で開いた端末）で実行する。

```bash
hostname -I
```

出力例:

```
192.168.1.10 172.17.0.1
```

**最初に表示されるIP**（この例では `192.168.1.10`）がサーバーのIP。
**このIPを紙かスマホにメモする。以降 `<サーバーIP>` と表記する。**

| 出てきたIP | 意味 |
|-----------|------|
| `192.168.x.x` / `10.x.x.x` | 家庭・学内LANのIP → **これを使う** |
| `172.17.x.x` | Dockerの内部IP → 使えない（コンテナ内で実行している） |
| `127.0.0.1` | 自分自身 → 使えない |

### 1-8. 自分自身への疎通確認

```bash
curl http://localhost:8080/status
```

`{"sales_count": 0, "total_amount": 0, "latest_event": "None"}` が返ればサーバーは正常。

### 1-9. ファイアウォールで8080を開放

```bash
sudo ufw allow 8080
```

パスワードを聞かれたら入力。`Rules updated` と出ればOK。
（ufwが無効の場合 `Firewall not enabled` 等が出るが、その場合は何もしなくてよい）

**→ Ubuntu側の準備完了。以降はラズパイ側の操作。**

---

## パート2: ラズパイ側（初回セットアップ）

### 2-1. ラズパイにログイン

直接操作するか、同じネットワークのPCからSSH:

```bash
ssh pi@<ラズパイのIP>
```

※ ユーザー名は環境に合わせる（`pi` とは限らない）

### 2-2. リポジトリを取得

初回のみ:

```bash
cd ~
git clone git@github.com:riririnn/AdvSoftwereG5.git
cd AdvSoftwereG5
```

2回目以降は:

```bash
cd ~/AdvSoftwereG5
git pull
```

※ clone で `Permission denied (publickey)` が出る場合はHTTPSを使う:
`git clone https://github.com/riririnn/AdvSoftwereG5.git`

### 2-3. Pythonバージョン確認

```bash
python3 --version
```

**3.10以上**であること（コードが `dict | None` 記法を使うため3.9以下では動かない）。
3.9以下の場合はDockerを使う（付録A参照）。

### 2-4. 必要なライブラリをインストール

```bash
pip3 install opencv-python-headless RPi.GPIO hx711
```

※ 重量センサーを使わない動作確認だけなら `opencv-python-headless` だけでもよい
（センサー系が無い場合は自動でダミー値になる）。

### 2-5. カメラ2台を接続して確認

USBカメラを2台ともUSBポートに挿してから:

```bash
ls /dev/video*
```

期待する出力（数字が2種類以上あればよい）:

```
/dev/video0  /dev/video1
```

※ 1台のカメラが `/dev/video0` と `/dev/video1` の2つを占有する機種もある。
その場合の見分け方:

```bash
v4l2-ctl --list-devices
```

（`v4l2-ctl` がなければ `sudo apt install v4l-utils`）
カメラ名ごとにデバイスが表示されるので、**各カメラの1番目のデバイス番号**をメモする。

### 2-6. どちらのカメラが何番かを決める

- **監視カメラ（人を映す）** → index 0 に接続されたカメラ
- **コイン・野菜カメラ（手元を映す）** → index 1 に接続されたカメラ

実際の番号が 0/1 でない場合（例: 0/2）は `app/config.py` の
`MONITOR_CAMERA_INDEX` / `COIN_CAMERA_INDEX` / `VEGETABLE_CAMERA_INDEX` を実番号に合わせる。

---

## パート3: ラズパイ側（接続設定と疎通確認）

### 3-1. サーバーIPを設定ファイルに書き込む

```bash
nano app/config.py
```

以下の行を探し（`Ctrl+W` で `PREDICT` を検索すると早い）:

```python
PREDICT_SERVER_URL = "http://localhost:8080"
```

パート1-7でメモしたIPに書き換える:

```python
PREDICT_SERVER_URL = "http://192.168.1.10:8080"
```

保存して終了: **`Ctrl+O` → `Enter` → `Ctrl+X`**

### 3-2. サーバーへの疎通確認

```bash
curl http://<サーバーIP>:8080/status
```

**成功**: `{"sales_count": 0, ...}` が返る → 3-3へ

**失敗パターンと対処**:

| エラー                            | 原因                               | 対処                                                    |
| --------------------------------- | ---------------------------------- | ------------------------------------------------------- |
| `Connection refused`              | サーバー未起動 or ポート違い       | Ubuntu側で `tmux attach -t server` で起動確認           |
| `No route to host` / タイムアウト | 別ネットワーク or ファイアウォール | 両方が同じWi-Fiか確認。Ubuntu側で `sudo ufw allow 8080` |
| `Could not resolve host`          | IPの打ち間違い                     | 1-7のIPを再確認                                         |

### 3-3. 静止画1枚で推論経路をテスト

カメラを使う前に、リポジトリ内のテスト画像で「ラズパイ→サーバー→JSON」の
全経路が動くことを確認する:

```bash
python3 app/simulate_raspi.py --image unattended_sales_place_images/selfsellingstation.jpg --server http://<サーバーIP>:8080
```

期待する出力（検出結果が表示される）:

```
[SimRPi] 画像モード: ... → http://192.168.1.10:8080/predict
  carrot  conf=45.57%  bbox=(52,362)-(96,387)
  corn    conf=45.20%  bbox=(92,423)-(164,498)
  ...
```

**これが出れば接続は完全に機能している。**

### 3-4. カメラからのリアルタイム送信テスト（任意だが推奨）

```bash
python3 app/simulate_raspi.py --camera 0 --server http://<サーバーIP>:8080
```

- カメラ0の映像が毎秒サーバーに送られ、検出結果が流れる
- **自分がカメラに映って `person` が表示されるか確認する**（人間検出の実写テスト）
- 終了は `Ctrl+C`（プレビューウィンドウがある環境では `q`）

※ SSH接続でGUIがない場合、プレビュー表示でエラーが出ることがある。
その場合も送信自体は動くので検出ログだけ確認すればよい。

---

## パート4: ラズパイ側（本番: controller起動）

### 4-1. tmuxを作って app/ ディレクトリへ移動

```bash
tmux new -s controller
cd ~/AdvSoftwereG5/app
```

### 4-2. controller起動

```bash
python3 controller.py
```

期待する出力:

```
[Controller] AIモードで起動します（推論サーバー: http://192.168.1.10:8080）
===================================
Unmanned Sales System
Waiting for customer...
===================================
```

この状態で、監視カメラの画像が約1秒おきにサーバーへ送られ、人待ちになる。

### 4-3. 動作シナリオを実行

1. **監視カメラ（index 0）の前に立つ**
   → `Customer detected.` → `Session started.` と表示され、録画が始まる
2. **コインカメラ（index 1）に硬貨を置く**（トレイに1枚ずつ、重ねない）
   → coin.csv に金額が記録される（100円玉が最も認識精度が高い）
3. **監視カメラの前から離れて3秒待つ**
   → `Customer left.` → 野菜認識・重量記録 → 万引き判定が自動実行され、
   `Theft Check Result` が表示される

### 4-4. 結果ファイルの確認

```bash
ls ~/AdvSoftwereG5/sessions/
```

日時名のフォルダ（例 `20260712_140503`）ができている。中身を確認:

```bash
cd ~/AdvSoftwereG5/sessions/<フォルダ名>
ls
# coin.csv  monitor.mp4  session.json  vegetable.csv  weight.csv

cat coin.csv        # 投入した硬貨が記録されているか
cat session.json    # "judgement": "normal" または "theft" が入っているか
```

### 4-5. 繰り返しテスト・終了

- controllerは自動で次の客待ちに戻るので、シナリオを何度でも繰り返せる
- 終了: `Ctrl+C`
- tmuxから抜ける（動かしたまま）: `Ctrl+b` → `d`／戻る: `tmux attach -t controller`

---

## パート5: Flask管理画面まで繋げる場合（ラズパイ側）

```bash
tmux new -s flask
cd ~/AdvSoftwereG5/Flask
python3 app.py
```

- `sessions自動監視を開始しました` と表示され、セッション完了から数秒で自動取込される
- ブラウザで `http://<ラズパイのIP>:5000` を開くと管理画面が見える
- 必要ライブラリ: `pip3 install flask`（LINE通知は担当者のトークン設定が必要）

---

## 付録A: Docker（ラズパイ）を使う場合

Python 3.10未満のラズパイや環境を汚したくない場合:

```bash
cd ~/AdvSoftwereG5
docker build -f .devcontainer/Dockerfile.rpi -t advsoftwareg5 .
bash scripts/start-container.sh          # カメラ・GPIOを自動でコンテナに渡す
docker exec -it advsoftwareg5_app bash   # コンテナに入る
cd app && python controller.py
```

## 付録B: よく使うコマンド早見表

| やりたいこと                   | コマンド                                                                         |
| ------------------------------ | -------------------------------------------------------------------------------- |
| サーバー画面に戻る（Ubuntu）   | `tmux attach -t server`                                                          |
| tmuxから抜ける（動かしたまま） | `Ctrl+b` → `d`                                                                   |
| サーバー疎通確認（ラズパイ）   | `curl http://<サーバーIP>:8080/status`                                           |
| 静止画テスト（ラズパイ）       | `python3 app/simulate_raspi.py --image <画像> --server http://<サーバーIP>:8080` |
| カメラテスト（ラズパイ）       | `python3 app/simulate_raspi.py --camera 0 --server http://<サーバーIP>:8080`     |
| 制御なしのキーボードモード     | `cd app && python3 controller.py --dummy`                                        |
| 重量センサー単体確認           | `cd app && python3 raspberry_pi.py`                                              |
| カメラデバイス一覧             | `v4l2-ctl --list-devices`                                                        |

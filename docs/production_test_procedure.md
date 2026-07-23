# 本番テスト 完全手順書（最初から最後まで）

これまでの結合テストで解決した全ての不具合（カメラ・録画・野菜判定・web_admin）を
踏まえた、**本番シナリオを通しで実行するための完全版手順書**。上から順に実施すれば
迷わず本番テストが完了する。

## 前提・全体構成

| 役割 | マシン | Tailscale IP |
|------|--------|-------------|
| 推論サーバー | rin-office（Ubuntu, GPU, DevContainer内） | **100.98.67.33** |
| ラズパイ | aseg1（Raspberry Pi 3 B+） | 100.120.189.9 |

- 作業ブランチ: **`integration-test`**（サーバー・ラズパイ両方）
- 接続は **Tailscale経由**（`localhost` や `192.168.x.x` は使わない）
- カメラ構成: 監視=`video0`（UVC Camera 046d:081b, C310, YUYV固定）/
  コイン・野菜=`video2`（C922 Pro Stream Webcam, 共用, MJPG）
- 判定は`app/config.py`の`TARGET_VEGETABLE`に設定された**1品目のみ**を
  重量ベースで判定する。テストする野菜は事前にこの品目に合わせておくこと
  （手順6で設定方法を説明）

---

## 1. 推論サーバー起動（🖥️ コンテナ内）

```bash
cd /workspace
tmux attach -t server   # 前回のセッションが残っていればこれで復帰
# セッションが無ければ:
tmux new -s server
python app/web_server.py
```

`Starting minimal web server on port 8080...` が出れば成功。`Ctrl+b` → `d` でデタッチ。

## 2. socat中継の起動（🖥️ Ubuntu本体 `rin@rin-office`）

🖥️コンテナ内で `hostname -I` を実行してコンテナのIPを確認し（例: 172.17.0.2）、
**山括弧なしで**そのIPを指定する:

```bash
socat TCP-LISTEN:8080,fork,reuseaddr TCP:172.17.0.2:8080 &
curl http://localhost:8080/status   # → {"sales_count": 0, ...} が返ればOK
```

⚠️ **このターミナルは閉じない。** 閉じると中継が止まりラズパイから繋がらなくなる。

## 3. ラズパイを最新化（🍓 ラズパイ）

`app/config.py`に`PREDICT_SERVER_URL`のTailscale IP設定がローカル変更として
残っているため、`git pull`前に必ず退避する。

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
git stash
git pull
git stash pop
```

`app/config.py`の差分を確認し、`PREDICT_SERVER_URL`が
`http://100.98.67.33:8080`になっていることを確認:

```bash
git diff config.py    # app/ディレクトリの中にいる場合。リポジトリルートなら app/config.py
```

疎通確認:

```bash
curl http://100.98.67.33:8080/status
```

## 4. カメラ動作確認（🍓 ラズパイ、任意・トラブル時のみ）

普段はスキップしてよい。異常が疑われる場合のみ実施:

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
python3 scripts/camera_diagnosis.py --cameras 0 2 --fps 10 --no-mjpg-cameras 0 2> /tmp/stderr.log
grep -c "Corrupt JPEG" /tmp/stderr.log
```

警告0件・両カメラとも550フレーム以上・read失敗0なら正常。
異常時は`docs/corrupt_jpeg_diagnosis.md`を参照。

## 5. web_adminを起動する（🍓 ラズパイ）

**本番テストで扱う野菜の商品登録を先に済ませるため、controllerより先にweb_adminを起動する。**

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
python3 -m web_admin.web_app
```

初回、以下のような出力が出る:

```
LED・ブザー・確認ボタンを初期化しました。
...
sessionsフォルダからWeb履歴を同期しました: 売上 N件, 通知 N件
sessions自動監視を開始しました: .../sessions
 * Running on http://192.168.x.x:5000
```

エラーが出る場合の対処:

- `ModuleNotFoundError: No module named 'flask'` → `sudo apt install -y python3-flask`
- `No module named 'web_admin'` → `app/`ディレクトリの中で実行しているか確認
- `permission denied`（`monitor_preview.jpg`等） →
  `sudo chown -R aseg1:aseg1 ~/advance_software_engnering/AdvSoftwareG5/sessions`
  （controllerをsudo実行、web_adminを非sudo実行することによるファイル所有者の不一致。
  実害はなく、繰り返し出続けることもない）

ターミナルを閉じたくない場合は`tmux`を使う:

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

## 6. テストする野菜を商品登録する（PCブラウザ、web_admin UI）

すでに登録済みの品目（トマト・なす等）でテストするなら本手順はスキップしてよい。
新しい野菜（例: りんご）で万引き判定まで正しく機能させたい場合は必須。

### 6-1. 商品登録

1. 画面上部ナビゲーション（スマホ表示は画面下部）から「**在庫**」を開く
2. 「**商品登録**」カード（画面左上、`＋`アイコン）で：
   - `productSelect`のプルダウンからテストする野菜を選択
     （47種類の候補から選べる。表示されない場合は`data_store.py`の
     不具合修正が反映されているか確認する）
   - 価格・在庫数・単重量を入力
   - 「＋ 登録」を押す

### 6-2. 重量センサーの判定対象を設定

`theft_checker.py`の重量ベース判定は`TARGET_VEGETABLE`に設定された
**1品目のみ**を見る。6-1で登録した野菜を実際にテストしたいなら、
この設定も合わせて変更する。

1. 同じ「在庫」ページの「**重量センサー設定**」カード（画面右側）
2. `sensor_1`の行のプルダウンで、6-1で登録した商品を選択
3. 「保存」ボタンを押す

保存すると`app/config.py`の`TARGET_VEGETABLE`が実際に書き換わる
（`POST /api/weight_sensors/target` → `data_store.export_to_config_py()`）。

⚠️ ラズパイ側の`config.py`が変わるため、**次にサーバーやweb_admin自体を
再起動する必要はない**（`controller.py`は起動のたびに`config.py`を読むので、
次回のセッションから反映される。すでに`controller.py`を起動したまま
待機している場合は、一度Ctrl+Cで止めて再起動すること）。

## 7. controller起動と本番シナリオ実行（🍓 ラズパイ、別ターミナル）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
sudo python3 controller.py
```

※ `sudo`のみでよい（GPIO・リアルタイム優先度切り替えのため）。

### シナリオ手順

1. **監視カメラ（video0）の前に立つ** → `Customer detected.` → `Session started.`
2. **野菜カメラ（video2）に、6で設定した野菜を置く**（入店時の在庫として記録）
3. **コインを置く**（1枚ずつ、重ねない。100円玉が高精度）
4. 万引きを試す場合は、セッション中に野菜を重量センサーの上から取り去る
5. **監視カメラの前から離れて3秒待つ** → `Customer left.` → 判定結果が表示される

### 成功条件

- [ ] `select() timeout` が出ない
- [ ] `Corrupt JPEG` が大量に出ない
- [ ] `coin.csv` に投入した硬貨が記録される
- [ ] `vegetable.csv` に before/after 両方が記録される
      （全部持ち去った場合はafterが`(none),0`のマーカー行。これは正常）
- [ ] `session.json` に `"judgement": "normal"` または `"theft"` が入る
      （`"error"`にならない）
- [ ] `monitor.mp4` の再生時間がセッションの実時間とほぼ一致する

### 結果確認（🍓 ラズパイ）

```bash
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/coin.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/weight.csv
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/session.json
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable_*.jpg
```

PCで動画・画像を見たい場合（PC側ターミナル）:

```bash
scp aseg1@100.120.189.9:~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/monitor.mp4 ./
scp "aseg1@100.120.189.9:~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/vegetable_*.jpg" .
```

## 8. web_admin側での反映確認（PCブラウザ）

手順5で起動したweb_adminは`sessions/`を5秒間隔で自動監視しているため、
手順7のセッション完了後、自動的に取り込まれる。

`http://100.120.189.9:5000` で以下を確認する:

- [ ] 「ホーム」の「最近の売上」または「最近の通知」に今回のセッションが出ている
- [ ] `normal`判定なら「在庫」ページで該当品目の在庫数が減っている
- [ ] `theft`判定なら「通知」ページに「万引き通知」が出ている
- [ ] LINE通知設定がしてあれば、LINEに通知が届いている

---

## 中断・再実施

```bash
Ctrl+C   # controllerは終了処理（録画スレッド停止・カメラ・GPIO解放）が自動で走る
```

作業内容はすべて`integration-test`ブランチにpush済みなので何も失われない。
次回は本手順書の「1. 推論サーバー起動」から再開すればよい。

## トラブル時の参照先

| 症状 | 参照先 |
|------|--------|
| カメラ関連（`Corrupt JPEG` / `select() timeout` / `can't open camera by index`） | `docs/corrupt_jpeg_diagnosis.md` |
| web_adminの既知の不具合・対応状況 | `app/web_admin/KNOWN_ISSUES.md` |
| その他の障害モードと対処表 | `docs/system_design.md` の「6. 既知の障害モードと対処表」 |
| 通しの操作手順の別バージョン（旧版） | `docs/raspi_connection_guide.md` |

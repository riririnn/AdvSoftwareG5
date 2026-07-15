# 結合テスト 再開手順

完了済み：サーバー起動・ポート公開・疎通確認・静止画推論・カメラ2台特定・
重量センサー動作確認（コイン/野菜とも計測成功）。

**現在地: カメラ2台同時使用時のタイムアウト対策（MJPG化）を実装済み。
その効果検証と、本番シナリオ1周の完走が残っている。**

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

## 4. カメラ2台同時テスト（🍓 ラズパイ、MJPG修正の効果検証）

controller起動前に、修正の効果を単体で確認する。
**2台同時に60秒読み続けて、タイムアウトが出ないこと**を見る:

```bash
python3 -c "
import cv2, time, threading

def watch(idx, results):
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 10)
    ok_count = fail_count = 0
    start = time.time()
    while time.time() - start < 60:
        ret, _ = cap.read()
        if ret: ok_count += 1
        else:
            fail_count += 1
            print(f'[video{idx}] {time.time()-start:.1f}s 失敗')
    cap.release()
    results[idx] = (ok_count, fail_count)

results = {}
t0 = threading.Thread(target=watch, args=(0, results))
t2 = threading.Thread(target=watch, args=(2, results))
t0.start(); t2.start(); t0.join(); t2.join()
for idx, (ok, ng) in results.items():
    print(f'video{idx}: 成功{ok} 失敗{ng}')
"
```

- **両方とも失敗0** → 対策有効。手順5へ
- **失敗が出る** → `cv2.VideoWriter_fourcc(*'MJPG')` の行を消して再実行し、
  失敗が増えるか比較した結果を報告する（原因の再切り分けに使う）

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

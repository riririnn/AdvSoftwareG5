# 結合テスト 再開手順

前回はここまで完了済み：サーバー起動・ポート公開・ラズパイのセットアップ・
疎通確認・静止画推論テスト・カメラ2台の特定。**重量センサーの配線確認で中断中。**

再開時は以下の手順だけを上から実行すればよい。

## この構成の実機情報

| 役割 | マシン | Tailscale IP |
|------|--------|-------------|
| 推論サーバー | rin-office（Ubuntu, GPU, DevContainer内） | **100.98.67.33** |
| ラズパイ | aseg1（Raspberry Pi OS） | 100.120.189.9 |

- 作業ブランチ: **`integration-test`**（サーバー・ラズパイ両方）
- 接続は **Tailscale経由**（`localhost` や `192.168.x.x` は使わない）
- カメラ設定（`app/config.py`、設定済み）: 監視=`video0` / コイン・野菜=`video2`

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

前回のターミナルを閉じていれば中継は止まっているので、再度張る:

```bash
# コンテナのIPを確認（🖥️コンテナ内で hostname -I）
socat TCP-LISTEN:8080,fork,reuseaddr TCP:<コンテナのIP>:8080 &
```

確認:

```bash
curl http://localhost:8080/status   # → {"sales_count": 0, ...} が返ればOK
```

⚠️ **このターミナルは閉じない。** 閉じると中継が止まりラズパイから繋がらなくなる。

## 3. ラズパイを最新化（🍓 ラズパイ）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5
git pull
```

---

## 4. 重量センサーの原因切り分け（🍓 ラズパイ、ここから未完了）

前回、`python3 raspberry_pi.py` が無反応でハングした。HX711は電源が来ていないと
DOUTの応答を待ち続けて永久にフリーズする仕組みのため、まず配線を疑う。

### 4-1. 配線確認

コイン用センサーの配線をチェック:

| HX711のピン | 接続先（ラズパイ、BCM番号） |
|------------|---------------------------|
| VCC | 5V または 3.3V |
| GND | GND |
| DT (DOUT) | GPIO16 |
| SCK (PD_SCK) | GPIO20 |

特にVCC/GNDの接続と、コイン用配線がGPIO16/20（野菜用のGPIO12/21と混同していないか）を確認する。

### 4-2. タイムアウト付き診断

配線を直したら、フリーズせず5秒でエラーが出るか確認:

```bash
python3 -c "
import RPi.GPIO as GPIO
from hx711 import HX711
import signal

def timeout_handler(signum, frame):
    raise TimeoutError('5秒応答なし。配線(特にVCC/GND)を確認')

GPIO.setmode(GPIO.BCM)
hx = HX711(dout_pin=16, pd_sck_pin=20)
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(5)
try:
    data = hx.get_raw_data(3)
    signal.alarm(0)
    print('取得成功:', data)
except TimeoutError as e:
    print('❌', e)
"
```

`取得成功: [数値, 数値, 数値]` が出れば配線OK。次のステップへ。

### 4-3. センサー単体確認

```bash
cd app
python3 raspberry_pi.py
```

`【コイン】: xxx g || 【野菜】: xxx g` が0.5秒ごとに表示されればOK（`Ctrl+C`で終了）。

### 4-4. スケール校正（未実施・要対応）

表示される値は仮の係数（`COIN_SCALE_RATIO=1880`, `VEGE_SCALE_RATIO=1000`,
`TARE_VEGE_PLATFORM=148.0`）を使っており、実機では校正されていない。
既知の重さの物（硬貨・分銅）を乗せ、`app/raspberry_pi.py` の該当定数を
実測値に合わせて調整する。

---

## 5. controller起動（🍓 ラズパイ、重量センサー確認後）

```bash
cd ~/advance_software_engnering/AdvSoftwareG5/app
tmux new -s controller
python3 controller.py
```

`[Controller] AIモードで起動します（推論サーバー: http://100.98.67.33:8080）` と出て人待ちになる。

### 動作シナリオ

1. **監視カメラ（video0）の前に立つ** → `Customer detected.` → `Session started.`
2. **コイン・野菜カメラ（video2）に硬貨を置く**（1枚ずつ、重ねない。100円玉が高精度）
3. **監視カメラの前から離れて3秒待つ** → `Customer left.` → 万引き判定結果が表示

### 結果確認

```bash
ls ~/advance_software_engnering/AdvSoftwareG5/sessions/
cat ~/advance_software_engnering/AdvSoftwareG5/sessions/<フォルダ名>/coin.csv
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
Ctrl+C   # 動いているプログラムを止める（controller.py, raspberry_pi.py など）
```

作業内容はすべて `integration-test` ブランチにpush済みなので何も失われない。
次回は本手順書の「1. サーバー再起動」から再開すればよい。

---

## よく使うコマンド早見表

| やりたいこと | 端末 | コマンド |
|-------------|------|---------|
| サーバー画面に戻る | 🖥️コンテナ | `tmux attach -t server` |
| tmuxから抜ける | 共通 | `Ctrl+b` → `d` |
| サーバー生存確認（curl無し） | 🖥️コンテナ | `python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/status').read())"` |
| ラズパイから疎通 | 🍓ラズパイ | `curl http://100.98.67.33:8080/status` |
| 静止画テスト | 🍓ラズパイ | `python3 app/simulate_raspi.py --image <画像> --server http://100.98.67.33:8080` |
| 重量センサー確認 | 🍓ラズパイ | `cd app && python3 raspberry_pi.py` |

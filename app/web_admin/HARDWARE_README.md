# Web UI ハードウェア表示機能

## 追加機能

- 購入判定（normal）: 緑LED点灯、赤LED消灯、ブザー停止
- 万引き判定（theft）: 赤LED点灯、緑LED消灯、ブザー鳴動継続
- 確認ボタン押下: ブザー停止
- LCD電子値札: app/config.py の sensor_1 商品情報を表示

## 配線例

| 部品 | GPIO |
|---|---:|
| 赤LED | GPIO17 |
| 緑LED | GPIO27 |
| ブザー | GPIO22 |
| 確認ボタン | GPIO23 |
| LCD SDA | GPIO2 |
| LCD SCL | GPIO3 |

確認ボタンは `GPIO23 -- ボタン -- GND` で接続します。
LEDには220Ω〜330Ω程度の抵抗を入れてください。

## 起動

```bash
pip install -r requirements.txt
python -m app.web_admin.web_app
```

GPIOやLCDライブラリが使えないWindows環境では、Web UIだけが起動し、ハードウェア制御は無効化されます。

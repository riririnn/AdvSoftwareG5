# LCD電子値札・商品登録 修正内容

## LCD表示

1602 LCDのA00文字マップを使用し、商品名と単位を半角カタカナで表示します。
YOLOの商品ラベル47種類をLCD用の半角カタカナ名へ変換しています。

アーモンドを150円・在庫10個・単重量100gで登録し、sensor_1に設定した場合:

```text
ｱｰﾓﾝﾄﾞ
1ｺ 100ｸﾞﾗﾑ 150ｴﾝ
```

LCDには在庫数ではなく、商品1個当たりの重量と価格を表示します。
在庫数はWeb管理画面側で引き続き管理します。

商品を削除した場合、またはsensor_1が未設定の場合:

```text
ｼｮｳﾋﾝ ﾅｼ
ｾﾝｻｰ ﾐｾｯﾃｲ
```

表示時は各行を16文字にそろえて空白で上書きし、前の文字が残らないようにしています。
また、自動改行を無効にし、1行目・2行目の座標を直接指定します。

通常は次の形式を使用します。

```text
1ｺ <重量>ｸﾞﾗﾑ <価格>ｴﾝ
```

数値が大きく16文字を超える場合は、表示の末尾が欠けないよう `ｸﾞﾗﾑ` を `g` に短縮します。

## 文字制限

LCDへ送る文字は次の範囲に限定しています。

- ASCIIの表示可能文字
- 半角カタカナ

ひらがな、漢字、全角カタカナなどが誤って渡された場合は `?` へ置き換えます。
半角カタカナを全角へ変換しないよう、LCD表示部分ではNFKC正規化を行いません。

## 商品登録

`config.py` にトマトしか残っていない状態でも、管理画面の商品候補には47種類すべてを表示します。
既存の `runtime/web_admin/data_store.json` がトマトだけの状態でも、起動後の読み込み時に商品候補を自動補完します。

最初の商品を登録したとき、sensor_1が未設定なら、その商品をsensor_1へ自動設定します。
2件目以降の商品登録では、現在選択しているsensor_1の商品は変更しません。

## LCD設定

I2Cアドレスと文字マップは環境変数でも変更できます。
カタカナ表示には `A00` を使用してください。

```bash
export LCD_ADDRESS=0x3f
export LCD_CHARMAP=A00
python -m app.web_admin.web_app
```

I2Cアドレスが `0x27` のLCDでは次のように変更します。

```bash
export LCD_ADDRESS=0x27
export LCD_CHARMAP=A00
python -m app.web_admin.web_app
```

## 単体表示テスト

```bash
cd ~/advance_software_engnering/AdvSoftwareG5

python - <<'PY'
import time
from app.web_admin.hardware_display import setup_hardware, write_lcd

setup_hardware()
write_lcd("ｱｰﾓﾝﾄﾞ", "1ｺ 100ｸﾞﾗﾑ 150ｴﾝ")
time.sleep(10)
PY
```

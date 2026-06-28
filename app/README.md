# app/README.md

# 無人販売システム（app）

## 概要

このディレクトリは、無人販売システムの制御プログラムを配置するディレクトリです。

本システムは、

- 入店検知
- セッション開始
- 防犯カメラ録画
- 野菜認識
- コイン認識
- 重量取得
- ログ保存
- 退店検知
- 万引き判定プログラム起動

までを担当します。

万引き判定アルゴリズム自体は本ディレクトリでは行わず、
取得したログを後処理プログラムへ渡す構成になっています。

---

# ディレクトリ構成

```
app/

├── config.py
├── controller.py
├── csv_logger.py
├── launcher.py
├── recorder.py
├── raspberry_pi.py
├── test_controller.py
└── README.md
```

---

# システム全体の流れ

```
待機
 │
 ▼
人を検知
 │
 ▼
Session作成
 │
 ▼
録画開始
 │
 ▼
入店時野菜取得
 │
 ▼
入店時重量取得
 │
 ▼
コイン認識開始
 │
 ▼
退店待機
 │
 ▼
人が3秒間いない
 │
 ▼
コイン認識停止
 │
 ▼
退店後野菜取得
 │
 ▼
退店後重量取得
 │
 ▼
録画停止
 │
 ▼
session.json更新
 │
 ▼
万引き判定プログラム起動
 │
 ▼
待機へ戻る
```

---

# 各ファイルの役割

## controller.py

システム全体を制御するメインプログラムです。

役割

- 入店待機
- 人物検知
- セッション開始
- Recorder制御
- Raspberry Pi制御
- 野菜認識
- コイン認識
- CSV保存
- Session終了
- Launcher起動

各モジュールをまとめる役割のみを担当します。

---

## config.py

システム全体で使用する定数を管理します。

例

- カメラ番号
- セッション保存先
- 録画サイズ
- FPS
- コイン認識周期
- 人がいなくなった判定時間
- ファイル名

基本的に定数はこのファイルへ追加してください。

---

## csv_logger.py

ログ保存専用モジュールです。

担当する処理

- セッションフォルダ作成
- CSV作成
- session.json作成
- session.json更新
- coin.csv保存
- vegetable.csv保存
- weight.csv保存

controller.pyからのみ呼び出されることを想定しています。

---

## recorder.py

監視カメラ録画を担当します。

内部ではOpenCVの

```
cv2.VideoWriter
```

を利用しています。

保存先

```
sessions/<session_id>/monitor.mp4
```

---

## raspberry_pi.py

重量取得用インターフェースです。

現在はダミー実装です。

後から重量担当者が実装を差し替えることを想定しています。

controller.pyはこのモジュールしか呼び出さない設計になっています。

---

## launcher.py

後処理プログラムを起動します。

現在はダミー実装です。

将来的には

```
subprocess.run(...)
```

などで万引き判定プログラムを起動してください。

controller.pyからは

```python
launch(session_dir)
```

のみ呼び出します。

---

## test_controller.py

システム全体のダミーテストです。

以下を一括で確認できます。

- セッション作成
- CSV作成
- session.json作成
- Recorder起動
- Recorder停止
- CSV保存
- Launcher起動

AI・ラズパイなしで動作確認できます。

---

# モジュール間の依存関係

```
controller.py
 │
 ├── config.py
 ├── recorder.py
 ├── csv_logger.py
 ├── raspberry_pi.py
 └── launcher.py
```

controller.pyのみが各モジュールを制御する構成です。

他モジュール同士が直接依存しないように設計しています。

---

# 現在ダミー実装になっている箇所

現在、以下はダミー実装です。

- raspberry_pi.py
- launcher.py
- 人物検知AI
- 野菜認識AI
- コイン認識AI

実装が完成次第、それぞれ差し替えてください。

---
# セッション構成

セッション開始時に以下のフォルダを作成します。

```
sessions/

└── 20260701_153015/
    ├── monitor.mp4
    ├── coin.csv
    ├── vegetable.csv
    ├── weight.csv
    └── session.json
```

1セッションにつき1フォルダ作成されます。

---

# CSVフォーマット

## coin.csv

```
datetime,coin
```

例

```
2026-07-01 15:30:10,100
2026-07-01 15:30:10,500
2026-07-01 15:30:11,10
```

---

## vegetable.csv

```
datetime,phase,vegetable,count
```

phase

- before
- after

例

```
2026-07-01 15:30:05,before,eggplant,5
2026-07-01 15:30:20,after,eggplant,4
```

---

## weight.csv

```
datetime,phase,target,weight
```

phase

- before
- after

target

- vegetable
- coinbox

例

```
2026-07-01 15:30:05,before,vegetable,1830
2026-07-01 15:30:05,before,coinbox,900
2026-07-01 15:30:20,after,vegetable,1600
2026-07-01 15:30:20,after,coinbox,1510
```

---

# session.json

```
{
    "session_id": "...",
    "status": "running / finished",
    "video": "monitor.mp4",
    "start_time": "...",
    "end_time": "..."
}
```

status

- running
- finished

---

# AIインターフェース（予定）

**※最終仕様はAI担当者と相談して決定してください。**

現在は以下の形式を想定しています。

```
result = predict(model, frame)
```

返り値

```python
{
    "detections": [
        {
            "class_name": "...",
            "confidence": 0.95
        }
    ]
}
```

人物・野菜・コイン認識すべて同じ形式で返すことを想定しています。

controller.py は、この形式で返ってくることを前提に設計されています。

---

# Raspberry Piインターフェース（予定）

**※最終仕様は重量担当者と相談して決定してください。**

現在は以下の形式を想定しています。

```python
{
    "vegetable": 1840,
    "coinbox": 950
}
```

単位は g（グラム）です。

controller.py はこの辞書を受け取ることを想定しています。

---

# 実装担当者向け

## AI担当

実装していただくもの

- 人物検知
- 野菜認識
- コイン認識

原則として controller.py を変更せず、
インターフェースを合わせる形で実装してください。

仕様変更が必要な場合は担当者間で相談してください。

---

## Raspberry Pi担当

raspberry_pi.py のみ変更してください。

重量取得処理のみ実装してください。

原則として controller.py を変更せず、
インターフェースを合わせる形で実装してください。

仕様変更が必要な場合は担当者間で相談してください。

---

## 万引き判定担当

launcher.py を利用してください。

現在は

```
launch(session_dir)
```

のみ実装されています。

ここから

```
sessions/<session_id>
```

を読み込み、

- coin.csv
- vegetable.csv
- weight.csv
- session.json

を利用して万引き判定を行ってください。

---

# テスト方法

ダミー実装のみで動作確認できます。

```
python app/test_controller.py
```

確認できる内容

- セッション作成
- CSV作成
- session.json作成
- 録画開始
- ダミーデータ保存
- 録画終了
- session.json更新
- launcher起動

---

# 今後の実装予定

以下は現在ダミー実装です。

- 人物検知AI
- 野菜認識AI
- コイン認識AI
- Raspberry Pi通信
- 万引き判定プログラム

完成次第、各担当者が差し替えてください。

controller.py の大幅な変更は行わず、各モジュールを差し替えるだけで動作する設計を目指しています。

---

# 開発方針

本システムでは、各機能を独立したモジュールとして実装し、controller.py が全体を制御する構成を採用しています。

新しい機能を追加する場合は、可能な限り controller.py の変更を最小限にし、各モジュール内で実装してください。

また、インターフェースを統一することで、各担当者が独立して開発・テストできることを目的としています。
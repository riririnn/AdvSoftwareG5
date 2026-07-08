# AI認識モジュール

YOLOv8を用いた野菜・硬貨・人間の認識システム。学習・推論・データ収集の機能を提供する。

---

## ディレクトリ構成

```
ai/
├── train.py              # 学習スクリプト
├── inference.py          # 推論モジュール（外部から呼び出す窓口）
├── download_dataset.py   # Roboflowデータセットのダウンロード
├── dataset/
│   ├── data.yaml         # Roboflow付属の学習設定ファイル（クラス定義もここ）
│   ├── train/            # 学習データ
│   ├── valid/            # 検証データ
│   └── test/             # テストデータ
├── runs/
│   └── vegetables_v1/
│       └── weights/
│           ├── best.pt   # 学習済みモデル（最良エポック）
│           └── last.pt   # 学習済みモデル（最終エポック）
├── collected_images/     # カメラで収集した独自学習データ
└── weights/              # 外部から持ち込んだ重みファイル置き場
```

---

## 学習

### データセット

Roboflow `rin-yokoyama/unattended_sales_place` v4（56クラス）を使用。
野菜・果物・日本円硬貨（1〜500円）・紙幣（1000〜10000円）を統合したもの。
`ai/dataset/` に配置し、`data.yaml` で管理される。

```bash
# ダウンロード（APIキーは環境変数で渡す。コミット厳禁）
ROBOFLOW_API_KEY="<自分のAPIキー>" python ai/download_dataset.py
```

### 実行

```bash
# 学習
python ai/train.py --data ai/dataset/data.yaml

# 中断したチェックポイント(last.pt)から再開
python ai/train.py --data ai/dataset/data.yaml --resume

# 検証のみ
python ai/train.py --mode val --data ai/dataset/data.yaml
```

**注意**: 学習は必ず `tmux` の中で実行する（SSH切断で学習が止まるのを防ぐ）。

```bash
tmux new -s train
python ai/train.py --data ai/dataset/data.yaml
# Ctrl+b → d でデタッチ、tmux attach -t train で復帰
```

### モデル選択

`ai/train.py` の `BASE_MODEL` で変更する。

| モデル | パラメータ数 | 精度 | 備考 |
|---|---|---|---|
| `yolov8n.pt` | 3.2M | 低 | ラズパイ向け軽量 |
| `yolov8s.pt` | 11.2M | 中 | 人間検出用に使用中（事前学習済みのまま） |
| `yolov8m.pt` | 25.9M | 高 | **現在使用中**（野菜・硬貨の学習ベース） |

### 学習パラメータ

| パラメータ | 値 | 説明 |
|---|---|---|
| `EPOCHS` | 100 | 最大学習エポック数 |
| `IMG_SIZE` | 640 | 入力解像度 |
| `BATCH_SIZE` | 16 | バッチサイズ |
| `PATIENCE` | 20 | Early stopping閾値 |
| `amp` | False | AMPチェックがRTX 5060 Ti環境でハングするため無効化 |

### 学習結果（2026-07-04 完了、100エポック）

| 指標 | 値 |
|---|---|
| mAP50 | 0.822 |
| mAP50-95 | 0.541 |
| Precision / Recall | 0.993 / 0.993 |

---

## 推論

### モデル構成（2モデル並列）

| 役割 | モデル | 出力 |
|---|---|---|
| 野菜・硬貨・紙幣 | `runs/vegetables_v1/weights/best.pt`（自前学習） | `class_id` >= 0 |
| 人間 | `yolov8s.pt`（COCO事前学習済み・学習不要） | `class_id` = -1, `class_name` = "person" |

### inference.py の使い方

```python
from ai.inference import load_model, load_person_model, predict, predict_all

model = load_model()                # 起動時に1度だけ呼ぶ
person_model = load_person_model()  # 人間検出用（初回はyolov8s.ptを自動DL）

# 野菜・硬貨のみ
result = predict(model, "path/to/image.jpg")

# 野菜・硬貨・人間を同時検出（web_server.py はこちらを使用）
result = predict_all(model, person_model, "path/to/image.jpg")
```

### 戻り値の形式

```json
{
  "image": "image.jpg",
  "width": 640,
  "height": 480,
  "detections": [
    {
      "class_id": 2,
      "class_name": "100yen",
      "confidence": 0.85,
      "bbox": { "x1": 229, "y1": 226, "x2": 341, "y2": 288 }
    },
    {
      "class_id": -1,
      "class_name": "person",
      "confidence": 0.91,
      "bbox": { "x1": 10, "y1": 5, "x2": 300, "y2": 470 }
    }
  ]
}
```

| フィールド | 説明 |
|---|---|
| `class_id` | クラスID（`dataset/data.yaml` の `names` と対応。人間のみ -1） |
| `class_name` | クラス名（英語） |
| `confidence` | 信頼度（0.0〜1.0） |
| `bbox` | バウンディングボックス。`x1,y1`=左上、`x2,y2`=右下（実ピクセル座標） |

### numpy配列（カメラフレーム）を渡す場合

```python
import cv2
frame = cv2.imread("image.jpg")  # またはカメラからのフレーム
result = predict_all(model, person_model, frame)
```

---

## クラス定義

`ai/dataset/data.yaml` の `names` で管理する（56クラス）。
クラスを追加・変更する場合はRoboflow側でデータセットを更新し、新バージョンを
生成して `download_dataset.py` でダウンロードし直す。

主なクラス:

| カテゴリ | クラス例 |
|---|---|
| 硬貨 | `1yen` `5yen` `10yen` `50yen` `100yen` `500yen` |
| 紙幣 | `1000yen` `5000yen` `10000yen` |
| 野菜・果物 | `tomato` `cucumber` `eggplant` `bell pepper` `onion` など |
| 人間 | `person`（データセット外。COCO事前学習モデルで検出） |

---

## 動作確認済みの項目（2026-07-05 時点）

- `/predict` エンドポイント経由の推論（`app/simulate_raspi.py` で確認）
- 硬貨検出: テスト画像で 100yen×5枚 を正解ラベル通りに検出（conf 65〜86%）
- 野菜検出: onion等を検出（conf 30〜85%）
- 人間検出: エラーなく動作（人が写った画像での実証は未実施）

## 既知の課題

### 精度
- 信頼度30〜50%の低確度検出が混ざる
- **対策**: `predict()` の `conf` 閾値調整、または `yolov8l` での再学習
- 学習データがすべてRoboflowの公開データセットであり、実際の販売台環境との乖離がある
- **対策**: `ai/collected_images/` に実環境の画像を収集して追加学習する

### 人間検出の実証不足
- 人が写った画像でのテストが未実施（テスト画像に人が写っていないため）
- **対策**: 結合テスト時にカメラの前に立って確認する

### バウンディングボックスの重複
- 同一物体に対して複数の検出が重なる場合がある（NMS閾値の調整が必要な場合）
- **対策**: `predict()` の `conf` 引数を上げる（デフォルト0.25）か、`iou` 閾値を調整する

### モデルファイルの配布
- `ai/runs/vegetables_v1/weights/best.pt` はバックアップ目的でGit管理する（それ以外の `*.pt` は原則Git管理外）。

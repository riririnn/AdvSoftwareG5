# AI認識モジュール

YOLOv8を用いた野菜認識システム。学習・推論・データ収集の機能を提供する。

---

## ディレクトリ構成

```
ai/
├── train.py              # 学習スクリプト
├── inference.py          # 推論モジュール（外部から呼び出す窓口）
├── download_dataset.py   # Roboflowデータセットのダウンロード
├── configs/
│   └── vegetables.yaml   # クラス定義・データセットパス設定
├── dataset/
│   ├── data.yaml         # Roboflow付属の学習設定ファイル
│   └── train/images/     # 学習画像
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

[Roboflow: Vegetables v3](https://roboflow.com) の26クラスデータセットを使用。  
`ai/dataset/` に配置し、`data.yaml` で管理される。

### 実行

```bash
# Roboflowデータセットで学習（推奨）
python ai/train.py --data ai/dataset/data.yaml

# 検証のみ
python ai/train.py --mode val --data ai/dataset/data.yaml
```

### モデル選択

`ai/train.py` の `BASE_MODEL` で変更する。

| モデル | パラメータ数 | 精度 | 備考 |
|---|---|---|---|
| `yolov8n.pt` | 3.2M | 低 | 現在使用中。ラズパイ向け軽量 |
| `yolov8s.pt` | 11.2M | 中 | バランス型 |
| `yolov8m.pt` | 25.9M | 高 | PC/GPU環境推奨 |

### 学習パラメータ

| パラメータ | 値 | 説明 |
|---|---|---|
| `EPOCHS` | 100 | 最大学習エポック数 |
| `IMG_SIZE` | 640 | 入力解像度 |
| `BATCH_SIZE` | 16 | バッチサイズ |
| `PATIENCE` | 20 | Early stopping閾値 |

---

## 推論

### inference.py の使い方

フレームワークに依存しない推論→JSON変換の関数。APIサーバー・ラズパイどちらからでも呼び出せる。

```python
from ai.inference import load_model, predict

model = load_model()                        # 起動時に1度だけ呼ぶ
result = predict(model, "path/to/image.jpg")
```

### 戻り値の形式

```json
{
  "image": "image.jpg",
  "width": 640,
  "height": 480,
  "detections": [
    {
      "class_id": 4,
      "class_name": "broccoli",
      "confidence": 0.78,
      "bbox": {
        "x1": 120,
        "y1":  45,
        "x2": 380,
        "y2": 290
      }
    }
  ]
}
```

| フィールド | 説明 |
|---|---|
| `class_id` | クラスID（`vegetables.yaml` の `names` と対応） |
| `class_name` | クラス名（英語） |
| `confidence` | 信頼度（0.0〜1.0） |
| `bbox` | バウンディングボックス。`x1,y1`=左上、`x2,y2`=右下（実ピクセル座標） |

### numpy配列（カメラフレーム）を渡す場合

```python
import cv2
frame = cv2.imread("image.jpg")  # またはカメラからのフレーム
result = predict(model, frame)
```

---

## クラス定義

`ai/configs/vegetables.yaml` で管理する。野菜を追加・変更する場合はこのファイルのみ編集する。

推論時に表示・集計する対象は `target_names` の4種のみ:

| クラス名 | 日本語 |
|---|---|
| tomato | トマト |
| cucumber | きゅうり |
| eggplant | なす |
| bell pepper | ピーマン |

---

## 既知の課題

### 精度
- 現在 `yolov8n`（nano）を使用しており、誤検出・検出漏れが多い
- **対策**: `yolov8s` または `yolov8m` に切り替えて再学習する（Todo）
- 学習データがすべてRoboflowの公開データセットであり、実際の販売台環境との乖離がある
- **対策**: `ai/collected_images/` に実環境の画像を収集して追加学習する

### 推論APIの未整備
- 現状、外部から画像を送って推論するHTTPエンドポイントが存在しない
- `inference.py` はローカルファイルパスまたはnumpy配列のみ受け付ける
- **対策**: `app/web_server.py` に `POST /predict` エンドポイントを追加する

### ラズパイでの動作未確認
- 学習・推論ともにGPU環境（Ubuntu + RTX 5060 Ti）でのみ検証済み
- ラズパイ（ARM, CPU推論）での速度・精度は未測定
- **対策**: `yolov8n` + `imgsz=320` で速度優先のパラメータで検証する

### バウンディングボックスの重複
- 同一物体に対して複数の検出が重なる場合がある（NMS閾値の調整が必要な場合）
- **対策**: `predict()` の `conf` 引数を上げる（デフォルト0.25）か、`iou` 閾値を調整する

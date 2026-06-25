# 野菜データセット 収集・ラベル付けガイド

AI認識（野菜）の学習データを作るための手順。今週のクリティカルパス。
クラス定義は `ai/configs/vegetables.yaml` が唯一の正（現状4種：tomato/cucumber/eggplant/pepper）。
野菜を追加するときは yaml を編集してから、同じ id でラベル付けする。

## 1. 画像収集

`app/camera_capture.py` の収集ユーティリティを使う：

```bash
cd app
python camera_capture.py     # collect_training_images() が起動
# Enter: 1枚保存 / q: 終了
```

保存先: `ai/collected_images/`

**集め方のコツ（精度に直結）**
- 各クラス **最低数十枚**、できれば100枚以上。
- **多様性**を持たせる：照明（明/暗/影）、角度、距離、個数、背景、かごの山積み具合。
- 実運用に近い画角・カメラで撮る（本番2台カメラの俯瞰想定）。
- 重なり（遮蔽）のある写真も入れる。山積みは本番の主条件。

## 2. アノテーション（YOLO形式）

ツール候補：**Roboflow**（Web・分割やエクスポートが楽）/ labelImg / Label Studio。
出力は YOLO 形式の txt（画像1枚につき1ファイル、同名）：

```
<class_id> <cx> <cy> <w> <h>      # すべて0〜1に正規化、1行=1物体
```

- `class_id` は `vegetables.yaml` の id と完全一致させる（tomato=0 等）。
- **山積みの基準を統一**：個体が見分けられるものは各々に箱を付ける。隠れて種類が判別不能なものは付けない。
- ラベルの付け漏れ・id ずれは精度を大きく落とすので要注意。

## 3. ディレクトリ配置

`vegetables.yaml` の `train: images/train` / `val: images/val` に合わせる：

```
ai/dataset/
├── images/
│   ├── train/   # 学習用画像 (.jpg)
│   └── val/     # 検証用画像
└── labels/
    ├── train/   # 学習用ラベル (.txt, 画像と同名)
    └── val/     # 検証用ラベル
```

- train : val ≈ **8 : 2** で分割。
- 画像とラベルは**ファイル名を対応**させる（`img001.jpg` ↔ `img001.txt`）。

## 4. 学習・評価

```bash
python ai/train.py    # train() → validate() が走る
```

- ベースモデルは `yolov8n.pt`（軽量）。精度不足なら `yolov8s/m` に変更（`ai/train.py` の `BASE_MODEL`）。
- 評価指標 **mAP50 / mAP50-95** を確認。低ければ画像追加・データ拡張調整。
- 山積み・遮蔽対策の拡張（mosaic / mixup / copy_paste）は `ai/train.py` に設定済み。

## 5. 連携メモ

- 推論結果は `app/yolo_inference.py` の `InferenceResult.to_json()` で出力。
- **個数(`counts`)はAI検出の参考値**（山積み遮蔽で不正確）。確定個数は重量センサー（三井）側。YOLOの主目的は**種類の特定**。

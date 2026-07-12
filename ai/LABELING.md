# データセット 収集・ラベル付けガイド

学習データを追加・改善するための手順。ラベル付けは Roboflow 上で行う。
クラス定義は `ai/dataset/data.yaml` の `names`（Roboflowからダウンロードされる）が唯一の正。

## 1. 画像収集

`app/camera_capture.py` の収集ユーティリティを使う：

```bash
cd app
python camera_capture.py     # collect_training_images() が起動
# Enter: 1枚保存 / q: 終了
```

保存先: `ai/collected_images/`

**集め方のコツ（精度に直結）**
- 各クラス **最低数十枚**、できれば100枚以上
- **多様性**を持たせる：照明（明/暗/影）、角度、距離、個数、背景、かごの山積み具合
- 実運用に近い画角・カメラで撮る（本番の設置位置・俯瞰想定）
- 重なり（遮蔽）のある写真も入れる。山積みは本番の主条件
- 硬貨は表・裏の両方を撮る

## 2. ラベル付け（Roboflow）

1. [Roboflow](https://app.roboflow.com) の `rin-yokoyama/unattended_sales_place` プロジェクトを開く
2. **Upload** から `ai/collected_images/` の画像をアップロード
3. バウンディングボックスでラベル付け
   - クラス名は既存の `names` と**完全一致**させる（`100yen` と `coin_100` のような表記ゆれは別クラスになる）
   - 山積みの基準を統一：個体が見分けられるものは各々に箱を付け、隠れて種類が判別不能なものは付けない
4. **Generate New Version** で新バージョンを生成
   - Preprocessing: Auto-Orient ON / Resize 640×640
   - Augmentation: Flip水平 / Rotation ±15° / Brightness ±25%

## 3. ダウンロードと再学習

```bash
# ai/download_dataset.py の VERSION を新バージョン番号に更新してから
ROBOFLOW_API_KEY="<自分のAPIキー>" python ai/download_dataset.py

# 学習（必ずtmux内で。SSH切断による学習停止を防ぐ）
tmux new -s train
python ai/train.py
```

評価指標 **mAP50 / mAP50-95** が学習後に表示される。低ければ画像追加・データ拡張調整。

## 4. 注意事項

- 日本円と形状が似た外国硬貨のデータは混ぜない（誤検出の原因になる）
- 人間（person）はラベル付け不要。COCO事前学習済みモデルで検出するためデータセットに含めない
- **個数はAI検出の参考値**（山積み遮蔽で不正確）。確定個数は重量センサー（三井）側。YOLOの主目的は**種類の特定**

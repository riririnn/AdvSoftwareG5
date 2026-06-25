# Advanced Software Engineering - Team Project (G5)

応用ソフトウェア工学のPBL（プロジェクトベース学習）チーム開発リポジトリ。  
無人販売所における野菜の認識・購入検知・万引き検知システムを構築する。

---

## システム概要

カメラ映像でYOLOv8による野菜認識を行い、重量センサーと照合することで購入・万引きを判定し、外部へ通知する。

```
カメラ映像
    │
    ▼
[app/camera_capture.py]  ← フレーム取得・防犯画像保存
    │ numpy配列
    ▼
[app/yolo_inference.py]  ← リアルタイム推論・個数集計
    │ InferenceResult (JSON)
    ▼
[app/main.py]            ← 重量センサーとの照合・万引き判定
    │
    ├─ 正常購入 → [app/web_client.py] → POST /update_sales
    └─ 異常検知 → アラート送信

[app/web_server.py]      ← GET /status, POST /update_sales
[ai/inference.py]        ← 単発推論API（外部から画像を受け取る窓口）
```

---

## ディレクトリ構成

```
/
├── app/
│   ├── main.py              # システム統括・万引き判定ロジック
│   ├── camera_capture.py    # カメラ映像取得・フレームストリーミング
│   ├── yolo_inference.py    # リアルタイム推論・バウンディングボックス描画
│   ├── web_server.py        # 軽量HTTPサーバー（標準ライブラリのみ）
│   └── web_client.py        # 外部へのPOST通知クライアント
├── ai/
│   ├── README.md            # AIモジュールの詳細ドキュメント
│   ├── train.py             # YOLOv8学習スクリプト
│   ├── inference.py         # 推論→JSON変換モジュール
│   ├── configs/
│   │   └── vegetables.yaml  # クラス定義・対象野菜設定
│   ├── dataset/             # Roboflowデータセット
│   └── runs/                # 学習済みモデル・ログ出力先
├── docs/                    # 設計資料・企画書
├── scripts/
│   └── start-container.sh   # コンテナ起動スクリプト（ラズパイ用）
└── .devcontainer/           # VS Code DevContainer設定
    ├── Dockerfile
    ├── devcontainer.json
    └── update-dependencies.sh
```

---

## 主要モジュールの役割

### app/camera_capture.py
OpenCVを用いてカメラ映像を取得し、フレームごとにコールバックへ渡す。

- `CameraCapture.stream(callback)` : フレームを連続取得してコールバックに渡す
- `CameraCapture.save_evidence(frame)` : 防犯用タイムスタンプ付き画像を `ai/collected_images/` に保存

### app/yolo_inference.py
リアルタイム推論・集計・描画を担う中核モジュール。

- `VegetableDetector.infer(frame)` : 1フレームを推論し `InferenceResult` を返す
- `InferenceResult.to_json()` : 重量センサー担当・万引き検知担当との連携用JSON
- 対象4種（トマト・きゅうり・なす・ピーマン）のみ集計し、他クラスは無視

### ai/inference.py
単発推論専用の軽量モジュール。Webエンドポイントやスクリプトから呼び出す。

```python
from ai.inference import load_model, predict
model = load_model()
result = predict(model, "image.jpg")  # dict形式でJSONが返る
```

詳細は [ai/README.md](ai/README.md) を参照。

### app/web_server.py
Python標準ライブラリのみで実装した軽量HTTPサーバー。

| エンドポイント | メソッド | 内容 |
|---|---|---|
| `/status` | GET | 売上カウント・最新イベントをJSON返却 |
| `/update_sales` | POST | 売上データを受け取り内部ステータスを更新 |

### app/web_client.py
`urllib` のみを使用した外部通知クライアント。

- `send_notification(message)` : 購入イベント・アラートをPOSTで送信

---

## 開発環境のセットアップ

### 必要なもの
- Ubuntu（WSLまたはSSH接続）
- Docker + NVIDIA Container Toolkit（GPU使用時）
- VS Code + Dev Containers拡張

### 起動手順

1. リポジトリをクローン
   ```bash
   git clone git@github.com:riririnn/AdvSoftwereG5.git
   cd AdvSoftwereG5
   ```

2. VS Codeで開き「Reopen in Container」を選択  
   （コマンドパレット: `Ctrl+Shift+P` → `Dev Containers: Reopen in Container`）

3. コンテナが起動したら学習を実行
   ```bash
   python ai/train.py --data ai/dataset/data.yaml
   ```

### GPU環境（devcontainer.json）

`runArgs` に以下が設定済みで、コンテナ内からホストのNVIDIA GPUを使用できる。

```json
"--gpus", "all",
"--cap-add=SYS_PTRACE",
"--security-opt", "seccomp=unconfined",
"--ipc=host"
```

---

## チーム開発フロー

1. `git pull` で最新を取得
2. `git checkout -b feature/xxx` でブランチを作成
3. DevContainer内で実装・テスト
4. `git push` → GitHub上でPRを作成 → `main` にマージ
5. ラズパイで `git pull` して実機テスト

---

## 既知の課題と今後のタスク

### AI認識精度

| 課題 | 状況 | 対策 |
|---|---|---|
| 誤検出・検出漏れが多い | 現在 `yolov8n`（最軽量）使用中 | `yolov8s` または `yolov8m` へ切り替え・再学習 |
| 実環境との乖離 | 公開データセットのみで学習 | 実販売台で画像収集して追加学習 |
| ラズパイでの動作未確認 | GPU環境のみ検証済み | `yolov8n + imgsz=320` で速度検証が必要 |

### Webシステム

| 課題 | 状況 | 対策 |
|---|---|---|
| 画像受信エンドポイントなし | `/predict` が未実装 | `web_server.py` に `POST /predict` を追加 |
| リアルタイム推論との連携なし | `yolo_inference.py` とWebが独立 | `main.py` でスレッド統合が必要 |
| 動画ストリーム未対応 | 静止画のみ | フレーム分割して逐次推論する仕組みが必要 |

### システム統合

| 課題 | 状況 | 対策 |
|---|---|---|
| 重量センサーとの照合未実装 | `check_purchase_or_theft()` はスタブのみ | センサー担当と連携して実装 |
| カメラなし環境でのテスト困難 | ハードウェア依存 | ダミーフレーム注入によるテスト機構が必要 |
| `app/` の import パスがローカル依存 | `from camera_capture import` 等 | `app/` をパッケージ化するか実行ディレクトリを統一 |

---

## 関連ドキュメント

- [ai/README.md](ai/README.md) : AIモジュール（学習・推論）の詳細
- [docs/app.md](docs/app.md) : Webシステム設計資料

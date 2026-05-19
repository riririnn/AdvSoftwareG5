# Advanced Software Engineering - Team Project

応用ソフトウェア工学のPBL（プロジェクトベース学習）におけるチーム開発用リポジトリです。

## 🎯 Project Goal
- 無人販売におけるお金の支払い問題を手助けするシステムを構築します。
- Raspberry PiのGPIO・SPI通信を用いたセンサー制御（磁気・重量）と、カメラを用いたAI画像認識（お金の枚数計算・野菜のラベリング分類）を組み合わせ、購入や万引きの認識と外部への通知を自動化します。

## 🛠 Tech Stack & Environment
* **Language:** Python 3.9
* **Environment:** Ubuntu (WSL) / Docker (Dev Containers)
* **Target Area:** IoT / AI
* **Infrastructure:** Local Raspberry Pi (OS Lite 32bit / Debian Bullseyeベース)
  
## 📂 Repository Structure
* `/app`: メインのアプリケーションコード（WebAPI、IoT制御、AI推論など）
* `/notebooks`: データ分析や機械学習モデルの実験用Jupyter Notebook
* `/docs`: 企画書、アーキテクチャ図、プレゼン資料
* `.devcontainer`: VS Code用のDocker環境設定ファイル
* `/docker`: 環境構築用の `Dockerfile` が含まれるディレクトリ
* `/scripts`: コンテナ起動用のシェルスクリプト (`start-container.sh`) が含まれるディレクトリ

## 🚀 Getting Started

1. **リポジトリのクローン**
   ```bash
   git clone git@github.com:riririnn/AdvSoftwereG5.git 
   cd AdvSoftwereG5
2. Dockerイメージのビルド
   `docker/Dockerfile` には、GPIO・カメラ操作に必要な依存パッケージ（`libi2c-dev, v4l-utils`）と、AI推論用の軽量ライブラリ（`tflite-runtime, opencv-python-headless`）が含まれています。
   以下のコマンドで、スクリプトに指定されている名前（`advsoftwareg5:latest`）でイメージをビルドします。
   ```s
   docker build -t advsoftwareG5:latest -f docker Dockerfile .
   ```
3. コンテナの起動
   `scripts/start-container.sh`を使用してコンテナを起動します。
   このスクリプトは、既存の`advsoftwareg5`コンテナが存在する場合は自動的に停止・削除し、ハードウェアデバイスへのアクセス権限（GPIO: `/dev/gpiomem`, SPI: `/dev/spidev0.0`, `/dev/spidev0.1`, カメラ: `/dev/video0`）を付与して起動します。
   ```s
   # 実行権限の付与（初回のみ）
   chmod +x scripts/start-container.sh
   # スクリプトの実行
   ./scripts/start-container.sh
   ```
4.
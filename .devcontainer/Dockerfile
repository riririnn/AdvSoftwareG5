# 1. ベースイメージの選定
# マルチアーキテクチャ対応の公式イメージを使用。
# PC(WSL/x86_64)環境と、ラズパイ(ARM32v7)環境の両方で自動的に最適化されます。
FROM python:3.9-slim-bullseye

# 環境変数の設定（Pythonのキャッシュ未生成化、ログの即時出力）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 作業ディレクトリの設定
WORKDIR /workspace

# 2. システムパッケージのインストール
# 講義資料の libi2c-dev や、GPIO・カメラ・OpenCVに必要な依存関係を網羅
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libi2c-dev \
    v4l-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \ 
    # Gitはソースコード管理のためにインストール（ Raspberry Pi 実行時には削除するか，RasPi専用のイメージを作成して Git を含めないようにすることも検討可能 )
    openssh-client \
    # OpenSSHクライアントは、リモートデバッグやコードのリモート管理に便利ですが、セキュリティ上の理由から、必要に応じてインストールするかどうかを検討してください。
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Pythonパッケージのインストール
# PC(WSL)環境でのビルド失敗を防ぐため、ハードウェア依存ライブラリ（RPi.GPIO, spidev）は
# ラズパイ（ARM環境）でのビルド時のみインストールされるように制御（環境の標準化）
RUN pip install --no-cache-dir --upgrade pip && \
    if [ "$(uname -m)" = "armv7l" ] || [ "$(uname -m)" = "aarch64" ]; then \
    pip install --no-cache-dir RPi.GPIO spidev; \
    else \
    echo "PC環境（WSL）を検知したため、ラズパイ専用ライブラリのインストールをスキップします。"; \
    fi

# 画像認識用の軽量パッケージ（講義要件の Minimal Web 準拠のため requests は除外）
RUN pip install --no-cache-dir \
    opencv-python-headless \
    tflite-runtime

# 開発時はホストのフォルダが自動マウントされるため、
# 以下はラズパイ実機でのスタンドアロン起動時（本番）のために残しておきます
COPY . /workspace

# 実行コマンド（メインループの起動）
CMD ["python", "main.py"]
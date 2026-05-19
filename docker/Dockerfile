# 1. ベースイメージの選定
# 添付資料の環境（Debian Bullseyeベースの32bit OS）に合わせて、Python 3.9のスリム版を使用
# FROM arm32v7/python:3.9-slim-bullseye(WSLでは動かないため、通常のpython:3.9-slim-bullseyeを使用(RaspberryPi上でビルドする場合はarm32v7/python:3.9-slim-bullseyeを使用))
FROM python:3.9-slim-bullseye

# 環境変数の設定（Pythonがキャッシュを書き込まない、ログを即時出力するなど）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 作業ディレクトリの設定
WORKDIR /app

# 2. システムパッケージのインストール
# 講義資料にある libi2c-dev や、GPIO・カメラ・OpenCVに必要な依存関係をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libi2c-dev \
    v4l-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Pythonパッケージのインストール
# 講義資料で指定されている RPi.GPIO や spidev に加え、画像認識と通知に必要なライブラリを追加
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    RPi.GPIO \
    spidev \
    opencv-python-headless \
    requests

# Raspberry Pi 3のスペック（リソース制限）を考慮し、軽量な推論エンジン（TFLite等）を推奨
# 必要に応じて、以下のようにtflite-runtime等を追加します
RUN pip install --no-cache-dir tflite-runtime

# 4. アプリケーションコードのコピー
COPY . /app

# 実行コマンド（例: main.py を実行）
CMD ["python", "main.py"]
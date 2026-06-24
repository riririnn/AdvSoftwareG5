FROM python:3.9-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libi2c-dev \
    v4l-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    openssh-client \
    tmux \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ラズパイ専用ライブラリはARM環境のみインストール
RUN pip install --no-cache-dir --upgrade pip && \
    if [ "$(uname -m)" = "armv7l" ] || [ "$(uname -m)" = "aarch64" ]; then \
        pip install --no-cache-dir RPi.GPIO spidev; \
    else \
        echo "PC環境を検知。ラズパイ専用ライブラリはスキップします。"; \
    fi

# Pythonパッケージ（開発・学習・推論に必要なものをすべてここに集約）
RUN pip install --no-cache-dir \
    opencv-python-headless \
    pyyaml \
    ultralytics

COPY . /workspace

CMD ["python", "app/main.py"]

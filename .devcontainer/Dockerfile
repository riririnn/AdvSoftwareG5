FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

# CUDA環境変数
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=/usr/local/cuda/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# システムパッケージ
RUN rm /etc/apt/sources.list.d/cuda.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    openssh-client \
    tmux \
    libi2c-dev \
    v4l-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    python3-pip \
    python3-dev \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# PyTorch（CUDA 12.8対応版）
RUN pip3 install --no-cache-dir \
    torch \
    torchvision \
    --index-url https://download.pytorch.org/whl/cu128

# Pythonパッケージ（開発・学習・推論に必要なものをすべてここに集約）
RUN pip3 install --no-cache-dir \
    opencv-python-headless \
    pyyaml \
    ultralytics \
    roboflow

# ラズパイ専用ライブラリはARM環境のみインストール
RUN if [ "$(uname -m)" = "armv7l" ] || [ "$(uname -m)" = "aarch64" ]; then \
    pip3 install --no-cache-dir RPi.GPIO spidev; \
    else \
    echo "PC環境を検知。ラズパイ専用ライブラリはスキップします。"; \
    fi

# 本番（ラズパイ実機）用。開発時はホストフォルダがマウントされるため上書きされる
COPY . /workspace

CMD ["python", "app/main.py"]

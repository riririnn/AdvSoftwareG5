#!/bin/bash

# --- 設定項目 ---
IMAGE_NAME="unmanned-sales-system:latest"
CONTAINER_NAME="unmanned_sales_app"

echo "========================================="
echo " Starting Docker Container: ${CONTAINER_NAME}"
echo "========================================="

# 1. 既存の同名コンテナが動作中または残っている場合は停止・削除する
if [ "$(docker ps -aq -f name=^${CONTAINER_NAME}$)" ]; then
    echo "Existing container found. Stopping and removing..."
    docker stop ${CONTAINER_NAME} >/dev/null 2>&1
    docker rm ${CONTAINER_NAME} >/dev/null 2>&1
fi

# 2. デバイスの存在チェックとオプションの組み立て
DEVICE_OPTS=""

# GPIOアクセス用のデバイスチェック
if [ -e /dev/gpiomem ]; then
    DEVICE_OPTS="${DEVICE_OPTS} --device /dev/gpiomem"
else
    echo "Warning: /dev/gpiomem not found. GPIO might not work."
fi

# SPI通信用（MCP3008等）のデバイスチェック
if [ -e /dev/spidev0.0 ]; then
    DEVICE_OPTS="${DEVICE_OPTS} --device /dev/spidev0.0"
fi
if [ -e /dev/spidev0.1 ]; then
    DEVICE_OPTS="${DEVICE_OPTS} --device /dev/spidev0.1"
fi

# カメラデバイス（画像認識用）のチェック
if [ -e /dev/video0 ]; then
    DEVICE_OPTS="${DEVICE_OPTS} --device /dev/video0"
else
    echo "Warning: /dev/video0 (Camera) not found. Image recognition will fail."
fi

# 3. Docker コンテナの起動
# --restart always: ラズパイの再起動時やプログラムが落ちた時に自動で再起動
echo "Running docker run with hardware access..."
docker run -d \
    --name "${CONTAINER_NAME}" \
    ${DEVICE_OPTS} \
    --restart always \
    "${IMAGE_NAME}"

# 4. 起動状態の確認
if [ $? -eq 0 ]; then
    echo "-----------------------------------------"
    echo "Container started successfully!"
    echo "To check logs, run: docker logs -f ${CONTAINER_NAME}"
    echo "-----------------------------------------"
else
    echo "Error: Failed to start container."
fi
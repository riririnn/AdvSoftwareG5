#!/bin/bash

echo "========================================="
echo " 同期中: DevContainer 開発環境チェック"
echo "========================================="

# パッケージの不足がないか、コンテナ起動時に念のため確認
pip install --no-cache-dir opencv-python-headless tflite-runtime

# もし将来的に requirements.txt を使う場合はここで自動インストール可能
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

echo "環境の初期化が完了しました。開発を始めてください！"
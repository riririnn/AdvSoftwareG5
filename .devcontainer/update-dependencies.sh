#!/bin/bash

echo "========================================="
echo " 同期中: DevContainer 開発環境チェック"
echo "========================================="

# コンテナ内のユーザー(root)とホストのファイル所有者が異なる場合に
# git が "dubious ownership" エラーを出すのを防ぐ
git config --global --add safe.directory /workspace

# ホストの ~/.gitconfig がマウントされていない場合のフォールバック
# コンテナ内でコミットするためにユーザー情報が必要
if [ -z "$(git config --global user.email)" ]; then
    echo "⚠️  git user.email が未設定です。以下を実行してください："
    echo "   git config --global user.email 'your@email.com'"
    echo "   git config --global user.name 'Your Name'"
fi

# パッケージの不足がないか、コンテナ起動時に念のため確認
pip install --no-cache-dir opencv-python-headless tflite-runtime

# もし将来的に requirements.txt を使う場合はここで自動インストール可能
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

echo "環境の初期化が完了しました。開発を始めてください！"
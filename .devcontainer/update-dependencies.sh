#!/bin/bash

echo "========================================="
echo " 同期中: DevContainer 開発環境チェック"
echo "========================================="

# git user 情報が未設定の場合に案内
if [ -z "$(git config --global user.email 2>/dev/null)" ]; then
    echo "⚠️  git user.email が未設定です。初回のみ以下を実行してください："
    echo "   git config --global user.email 'your@email.com'"
    echo "   git config --global user.name 'Your Name'"
fi

echo "環境の初期化が完了しました。開発を始めてください！"

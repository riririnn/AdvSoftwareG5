import os
import requests


LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")


def send_line_message(message):
    """
    LINE Messaging APIでメッセージを送信する
    今回はbroadcast送信を使用
    Botを友だち追加しているユーザーに送信される
    """
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("LINE channel access token is not set.")
        print(message)
        return False

    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    data = {
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        print("LINE notification sent.")
        return True
    else:
        print("Failed to send LINE notification.")
        print("Status code:", response.status_code)
        print(response.text)
        return False
import os
import requests


LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")


def send_line_message(message):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("LINE_CHANNEL_ACCESS_TOKEN が設定されていません。")
        return {
            "status": "error",
            "message": "LINE_CHANNEL_ACCESS_TOKEN が設定されていません。"
        }

    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        print("========== LINE TEXT RESULT ==========")
        print("LINE text status:", response.status_code)
        print("LINE text response:", response.text)
        print("======================================")

        if response.status_code == 200:
            print("LINE text notification sent.")
            return {
                "status": "success",
                "status_code": response.status_code,
                "response": response.text
            }

        print("LINE text notification failed.")
        return {
            "status": "error",
            "status_code": response.status_code,
            "response": response.text
        }

    except Exception as error:
        print("LINE送信中にエラーが発生しました:", error)
        return {
            "status": "error",
            "message": str(error)
        }


def send_line_video_message(text_message, video_url, preview_image_url):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("LINE_CHANNEL_ACCESS_TOKEN が設定されていません。")
        return {
            "status": "error",
            "message": "LINE_CHANNEL_ACCESS_TOKEN が設定されていません。"
        }

    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {
                "type": "text",
                "text": text_message
            },
            {
                "type": "video",
                "originalContentUrl": video_url,
                "previewImageUrl": preview_image_url
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        print("========== LINE VIDEO RESULT ==========")
        print("LINE video status:", response.status_code)
        print("LINE video response:", response.text)
        print("video_url:", video_url)
        print("preview_image_url:", preview_image_url)
        print("=======================================")

        if response.status_code == 200:
            print("LINE video notification sent.")
            return {
                "status": "success",
                "status_code": response.status_code,
                "response": response.text
            }

        print("LINE video notification failed.")
        return {
            "status": "error",
            "status_code": response.status_code,
            "response": response.text
        }

    except Exception as error:
        print("LINE動画送信中にエラーが発生しました:", error)
        return {
            "status": "error",
            "message": str(error)
        }

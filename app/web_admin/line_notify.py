from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
import hashlib
import mimetypes
import os
import shutil
import smtplib
import subprocess
from datetime import datetime

try:
    from .data_store import get_line_settings
except Exception:
    try:
        from data_store import get_line_settings
    except Exception:
        get_line_settings = None


# =========================================================
# メール送信用設定
# =========================================================
# 設定するのは、送信用メールアカウントだけです。
# 農家さんがWeb画面で設定するのは「通知先名」と「通知先メールアドレス」です。
# Gmailを使う場合、SMTP_PASSWORD には通常のログインパスワードではなく
# Googleアカウントで発行した「アプリパスワード」を入力してください。
# GitHubなどへ公開する場合は、本物のメールアドレスやパスワードを消してください。
SMTP_USERNAME = "sohutoweakogaku5@gmail.com"          # 例: "your_account@gmail.com"
SMTP_PASSWORD = "eera twcd hlyy pmop"          # 例: Gmailのアプリパスワード
SMTP_FROM_ADDRESS = ""      # 空の場合はSMTP_USERNAMEを使用
SENDER_NAME = "無人販売支援システム"

# Gmail送信用の固定設定です。通常は変更しなくて大丈夫です。
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USE_TLS = True

# Gmailの添付上限は環境により変わります。授業デモでは20MB以下を推奨します。
# 25MBぎりぎりだと送信で失敗することがあるため、20MB以下に圧縮して添付します。
MAX_ATTACHMENT_MB = 20

# 動画が大きい場合は、自動で圧縮してから添付します。
# メール添付容量を小さくするため、圧縮版では音声を削除します。
# 証拠確認用として長すぎる動画は先頭30秒に短縮します。
AUTO_COMPRESS_VIDEO = True
KEEP_AUDIO_IN_COMPRESSED_VIDEO = False
MAX_VIDEO_SECONDS_FOR_MAIL = 30
COMPRESSED_VIDEO_WIDTHS = [640, 480, 360, 320]
COMPRESSED_VIDEO_CRFS = [35, 38, 40, 42]
COMPRESSED_VIDEO_FPS = [15, 12, 10, 8]

# 環境変数にも対応します。コードに直接書きたくない場合に使えます。
ENV_SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
ENV_SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
ENV_SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", "").strip()


def get_mail_config():
    sender_email = ENV_SMTP_USERNAME or str(SMTP_USERNAME or "").strip()
    raw_password = ENV_SMTP_PASSWORD or str(SMTP_PASSWORD or "")
    # Googleのアプリパスワードは表示上4文字ごとに空白が入るため、
    # 前後だけでなく内部の空白もすべて除去してSMTP認証へ渡す。
    sender_password = "".join(raw_password.split())
    from_address = ENV_SMTP_FROM_ADDRESS or str(SMTP_FROM_ADDRESS or "").strip() or sender_email

    return {
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "use_tls": SMTP_USE_TLS,
        "sender_email": sender_email,
        "sender_password": sender_password,
        "from_address": from_address,
        "sender_name": SENDER_NAME,
    }


def get_notice_flag_names(notice_type):
    notice_type = str(notice_type or "system").strip()

    if notice_type in ["purchase", "購入通知"]:
        return ["purchase_notice"]

    if notice_type in ["theft", "万引き通知"]:
        return ["theft_notice"]

    if notice_type in ["theft_video", "video", "動画通知"]:
        return ["theft_notice", "video_notice"]

    return ["system_notice"]


def get_enabled_recipients(notice_type="system"):
    if get_line_settings is None:
        return []

    settings = get_line_settings()
    required_flags = get_notice_flag_names(notice_type)
    recipients = []

    for recipient in settings.get("recipients", []):
        if not recipient.get("enabled", True):
            continue

        email = str(recipient.get("email", "") or "").strip()
        if not email:
            continue

        if all(recipient.get(flag, False) for flag in required_flags):
            recipients.append(recipient)

    return recipients


def make_subject(notice_type):
    notice_type = str(notice_type or "system")
    if notice_type == "purchase":
        return "【無人販売支援システム】購入通知"
    if notice_type in ["theft", "theft_video", "video"]:
        return "【無人販売支援システム】万引き通知"
    return "【無人販売支援システム】システム通知"


def get_attachment_work_dir():
    work_dir = Path(__file__).resolve().parent / "mail_attachments"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def get_file_size_mb(path):
    return Path(path).stat().st_size / (1024 * 1024)


def make_compressed_video_path(source_path, label):
    source = Path(source_path).resolve()
    key_text = f"{source}|{source.stat().st_mtime_ns}|{source.stat().st_size}|{label}"
    key = hashlib.md5(key_text.encode("utf-8")).hexdigest()[:10]
    return get_attachment_work_dir() / f"{source.stem}_mail_{key}.mp4"


def compress_video_with_ffmpeg(source_path):
    """ffmpeg で音声なしの軽量動画に圧縮し、20MB以下を目指す。"""
    ffmpeg_cmd = shutil.which("ffmpeg")
    if not ffmpeg_cmd:
        return None, "ffmpeg が見つかりません。OpenCVで音声なし圧縮を試行します。"

    source = Path(source_path).resolve()
    last_message = ""

    for width, crf, fps in zip(COMPRESSED_VIDEO_WIDTHS, COMPRESSED_VIDEO_CRFS, COMPRESSED_VIDEO_FPS):
        output = make_compressed_video_path(source, f"ffmpeg_w{width}_crf{crf}_fps{fps}")

        if output.exists() and get_file_size_mb(output) <= MAX_ATTACHMENT_MB:
            return output, f"既存の圧縮済み動画を使用します: {output.name}"

        cmd = [
            ffmpeg_cmd,
            "-y",
            "-i", str(source),
            "-t", str(MAX_VIDEO_SECONDS_FOR_MAIL),
            "-map", "0:v:0",
            "-vf", f"scale='min({width},iw)':-2,fps={fps}",
            "-vcodec", "libx264",
            "-preset", "veryfast",
            "-crf", str(crf),
            "-an",  # 音声は削除してファイルサイズを小さくする
            "-movflags", "+faststart",
            str(output),
        ]

        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )
        except Exception as error:
            last_message = f"ffmpeg圧縮中にエラー: {error}"
            continue

        if completed.returncode != 0:
            last_message = completed.stderr[-500:] if completed.stderr else "ffmpeg圧縮に失敗しました。"
            continue

        if output.exists() and output.stat().st_size > 0:
            size_mb = get_file_size_mb(output)
            print(f"compressed by ffmpeg: {output} ({size_mb:.2f} MB)")
            if size_mb <= MAX_ATTACHMENT_MB:
                return output, f"動画を自動圧縮しました: {size_mb:.1f}MB"
            last_message = f"圧縮後も大きすぎます: {size_mb:.1f}MB"

    return None, last_message or "ffmpegで20MB以下に圧縮できませんでした。"


def compress_video_with_opencv(source_path):
    """ffmpeg がない場合の予備圧縮。OpenCVは音声を残せないため、通常は使用しない。"""
    try:
        import cv2
    except Exception as error:
        return None, f"OpenCVを読み込めません: {error}"

    source = Path(source_path).resolve()

    for width, fps_limit in [(480, 10), (360, 8), (320, 6)]:
        output = make_compressed_video_path(source, f"opencv_w{width}_fps{fps_limit}")

        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            return None, "OpenCVで動画を開けませんでした。"

        original_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        if original_width <= 0 or original_height <= 0:
            cap.release()
            return None, "動画の解像度を取得できませんでした。"

        scale = min(1.0, width / float(original_width))
        new_width = max(2, int(original_width * scale) // 2 * 2)
        new_height = max(2, int(original_height * scale) // 2 * 2)
        output_fps = min(float(original_fps), float(fps_limit))
        frame_interval = max(1, round(float(original_fps) / output_fps))
        max_frames = int(MAX_VIDEO_SECONDS_FOR_MAIL * original_fps)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output), fourcc, output_fps, (new_width, new_height))

        if not writer.isOpened():
            cap.release()
            writer.release()
            continue

        frame_index = 0
        written = 0
        while frame_index < max_frames:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_index % frame_interval == 0:
                frame = cv2.resize(frame, (new_width, new_height))
                writer.write(frame)
                written += 1

            frame_index += 1

        cap.release()
        writer.release()

        if output.exists() and output.stat().st_size > 0 and written > 0:
            size_mb = get_file_size_mb(output)
            print(f"compressed by OpenCV: {output} ({size_mb:.2f} MB)")
            if size_mb <= MAX_ATTACHMENT_MB:
                return output, f"動画を自動圧縮しました: {size_mb:.1f}MB"

    return None, "OpenCVでも20MB以下に圧縮できませんでした。"


def prepare_attachment_file(file_path):
    path = Path(str(file_path or "")).expanduser().resolve()

    print("========== MAIL ATTACH CHECK ==========")
    print("attachment path:", path)

    if not path.exists() or not path.is_file():
        print("attachment result: file not found")
        print("=======================================")
        return None, f"添付ファイルが見つかりません: {path}"

    size_mb = get_file_size_mb(path)
    print(f"attachment original size: {size_mb:.2f} MB")

    if size_mb <= 0:
        print("attachment result: empty file")
        print("=======================================")
        return None, f"動画ファイルが空です: {path}"

    if size_mb <= MAX_ATTACHMENT_MB:
        print("attachment result: original file is small enough")
        return path, f"添付しました: {path.name}"

    if not AUTO_COMPRESS_VIDEO or path.suffix.lower() != ".mp4":
        print("attachment result: file too large")
        print("=======================================")
        return None, f"添付ファイルが大きすぎます: {size_mb:.1f}MB（上限 {MAX_ATTACHMENT_MB}MB）"

    print("attachment result: too large, start auto compression")

    compressed_path, compress_message = compress_video_with_ffmpeg(path)
    if compressed_path is None:
        print("ffmpeg compression:", compress_message)
        compressed_path, compress_message = compress_video_with_opencv(path)

    if compressed_path is None:
        print("attachment result: compression failed")
        print("compression message:", compress_message)
        print("=======================================")
        return None, f"動画の自動圧縮に失敗しました。{compress_message}"

    compressed_size_mb = get_file_size_mb(compressed_path)
    print("compressed attachment path:", compressed_path)
    print(f"compressed attachment size: {compressed_size_mb:.2f} MB")

    if compressed_size_mb > MAX_ATTACHMENT_MB:
        print("attachment result: compressed file still too large")
        print("=======================================")
        return None, f"圧縮後も動画が大きすぎます: {compressed_size_mb:.1f}MB（上限 {MAX_ATTACHMENT_MB}MB）"

    print("attachment result: compressed and attached")
    return compressed_path, f"{compress_message} / 添付ファイル: {compressed_path.name}"


def attach_file(message, file_path):
    path, prepare_message = prepare_attachment_file(file_path)
    if path is None:
        return False, prepare_message

    content_type, _ = mimetypes.guess_type(str(path))

    # mp4は確実にvideo/mp4として添付する
    if path.suffix.lower() == ".mp4":
        maintype, subtype = "video", "mp4"
    elif content_type and "/" in content_type:
        maintype, subtype = content_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    with open(path, "rb") as file:
        message.add_attachment(
            file.read(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name
        )

    print("attachment result: attached")
    print("attachment mime:", f"{maintype}/{subtype}")
    print("attachment used path:", path)
    print("=======================================")
    return True, prepare_message

def send_mail_to_recipient(recipient, subject, body, attachment_path=None):
    config = get_mail_config()
    to_address = str(recipient.get("email", "") or "").strip()

    if not config["sender_email"] or not config["sender_password"]:
        return {
            "status": "error",
            "target": to_address,
            "message": "SMTP_USERNAME / SMTP_PASSWORD が設定されていません。"
        }

    if not to_address:
        return {
            "status": "error",
            "target": to_address,
            "message": "通知先メールアドレスが設定されていません。"
        }

    mail = EmailMessage()
    mail["Subject"] = subject
    mail["From"] = formataddr((config["sender_name"], config["from_address"]))
    mail["To"] = to_address
    mail.set_content(str(body))

    attachment_message = "添付なし"
    if attachment_path:
        attached, attach_message = attach_file(mail, attachment_path)
        attachment_message = attach_message
        if not attached:
            return {
                "status": "error",
                "target": to_address,
                "message": attach_message
            }

    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=20) as smtp:
            if config["use_tls"]:
                smtp.starttls()
            smtp.login(config["sender_email"], config["sender_password"])
            smtp.send_message(mail)

        print("========== MAIL SEND RESULT ==========")
        print("mail target:", to_address)
        print("mail subject:", subject)
        print("attachment:", attachment_path or "なし")
        print("======================================")

        return {
            "status": "success",
            "target": to_address,
            "message": "メールを送信しました。",
            "attachment": attachment_message
        }

    except Exception as error:
        print("メール送信中にエラーが発生しました:", error)
        return {
            "status": "error",
            "target": to_address,
            "message": str(error)
        }


def send_line_message(message, notice_type="system"):
    """互換性のため関数名は残し、中身はメール送信に変更。"""
    recipients = get_enabled_recipients(notice_type=notice_type)

    if not recipients:
        print("メール通知先が登録されていない、または通知がOFFです。")
        return {
            "status": "skipped",
            "message": "メール通知先が登録されていない、または通知がOFFです。"
        }

    results = []
    subject = make_subject(notice_type)
    for recipient in recipients:
        results.append(send_mail_to_recipient(recipient, subject, message))

    return {
        "status": "success" if any(r.get("status") == "success" for r in results) else "error",
        "notice_type": notice_type,
        "sent_count": sum(1 for r in results if r.get("status") == "success"),
        "target_count": len(results),
        "results": results
    }


def send_line_video_message(text_message, video_url=None, preview_image_url=None, video_path=None):
    """互換性のため関数名は残し、中身は動画添付メール送信に変更。"""
    recipients = get_enabled_recipients(notice_type="theft_video")

    if not recipients:
        print("動画メール通知先が登録されていない、または動画通知がOFFです。")
        return {
            "status": "skipped",
            "message": "動画メール通知先が登録されていない、または動画通知がOFFです。"
        }

    attachment_path = video_path or video_url
    subject = make_subject("theft_video")
    body = str(text_message) + "\n\n監視動画を添付しています。"

    results = []
    for recipient in recipients:
        results.append(send_mail_to_recipient(recipient, subject, body, attachment_path=attachment_path))

    return {
        "status": "success" if any(r.get("status") == "success" for r in results) else "error",
        "notice_type": "theft_video",
        "sent_count": sum(1 for r in results if r.get("status") == "success"),
        "target_count": len(results),
        "results": results
    }

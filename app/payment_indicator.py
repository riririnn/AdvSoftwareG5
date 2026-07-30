"""
支払い状態用LED・ブザー・確認ボタン制御。

GPIOの所有者を controller.py の1プロセスに限定し、Flask側との競合を防ぐ。
ファイルへの状態書き込みは行わないため、root/一般ユーザー間の権限問題も発生しない。

動作:
- 待機中: 白LED OFF / 赤LED OFF / 緑LED OFF / 黄LED OFF / ブザー OFF
- 来客検知中・商品未取得: 白LED ON / 赤LED OFF / 緑LED OFF / 黄LED OFF
- 商品取得後・支払い未確認: 白LED OFF / 赤LED ON / 緑LED OFF / 黄LED OFF
- 重量測定中（支払いは確認済み・重量判定はまだ）: 赤LED OFF / 緑LED OFF / 黄LED ON
- 支払い完了: 赤LED OFF / 緑LED ON / 黄LED OFF
- 退店後の未払い確定: 赤LED ON / 緑LED OFF / 黄LED OFF / ブザー ON
- 確認ボタン: ブザーのみ停止（赤LEDは維持）
"""

from __future__ import annotations

import threading

from config import (
    WHITE_LED_PIN,
    RED_LED_PIN,
    GREEN_LED_PIN,
    YELLOW_LED_PIN,
    BUZZER_PIN,
    CONFIRM_BUTTON_PIN,
)

try:
    from gpiozero import LED, Buzzer, Button
except Exception:
    LED = None
    Buzzer = None
    Button = None


_lock = threading.RLock()
_white_led = None
_red_led = None
_green_led = None
_yellow_led = None
_buzzer = None
_confirm_button = None
_available = False
_buzzer_alert_active = False
_last_display_signature = None


def setup() -> bool:
    """GPIOを初期化する。PC等では無効化して処理を継続する。"""
    global _white_led, _red_led, _green_led, _yellow_led, _buzzer, _confirm_button, _available

    if _available:
        return True

    if LED is None or Buzzer is None or Button is None:
        print(
            "[PaymentIndicator] gpiozeroが使えないため、"
            "LED・ブザー・確認ボタン制御は無効です。"
        )
        return False

    try:
        _white_led = LED(WHITE_LED_PIN)
        # 赤LEDのみ配線の極性が逆（アクティブLow）のため、論理を反転させる。
        _red_led = LED(RED_LED_PIN, active_high=False)
        _green_led = LED(GREEN_LED_PIN)
        _yellow_led = LED(YELLOW_LED_PIN)
        _buzzer = Buzzer(BUZZER_PIN)
        _confirm_button = Button(
            CONFIRM_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.1,
        )
        _confirm_button.when_pressed = stop_buzzer
        _available = True
        show_idle(reset_buzzer=True)

        print(
            "[PaymentIndicator] 初期化しました。"
            f"白LED=GPIO{WHITE_LED_PIN}, "
            f"赤LED=GPIO{RED_LED_PIN}, "
            f"緑LED=GPIO{GREEN_LED_PIN}, "
            f"黄LED=GPIO{YELLOW_LED_PIN}, "
            f"ブザー=GPIO{BUZZER_PIN}, "
            f"確認ボタン=GPIO{CONFIRM_BUTTON_PIN}"
        )
        return True

    except Exception as error:
        print(f"[PaymentIndicator] GPIO初期化に失敗しました: {error}")
        cleanup()
        return False


def show_idle(*, reset_buzzer: bool = False) -> None:
    """待機状態。通常はLEDのみ消灯し、警報ブザーは勝手に止めない。"""
    global _buzzer_alert_active, _last_display_signature

    with _lock:
        if _white_led:
            _white_led.off()
        if _red_led:
            _red_led.off()
        if _green_led:
            _green_led.off()
        if _yellow_led:
            _yellow_led.off()
        if reset_buzzer and _buzzer:
            _buzzer.off()
            _buzzer_alert_active = False
        _last_display_signature = ("idle",)


def show_pending(required_amount: int = 0, paid_amount: int = 0) -> None:
    """来客検知中・商品未取得。白LEDを点灯する。"""
    global _last_display_signature
    required_amount = int(required_amount)
    paid_amount = int(paid_amount)
    signature = ("pending", required_amount, paid_amount)

    with _lock:
        if _white_led:
            _white_led.on()
        if _red_led:
            _red_led.off()
        if _green_led:
            _green_led.off()
        if _yellow_led:
            _yellow_led.off()

    shortage = max(0, required_amount - paid_amount)
    if signature != _last_display_signature:
        print(
            "[PaymentIndicator] 来客検知: "
            f"必要{required_amount}円 / "
            f"投入{paid_amount}円 / "
            f"不足{shortage}円 / 白LED ON"
        )
        _last_display_signature = signature


def show_unconfirmed(required_amount: int = 0, paid_amount: int = 0) -> None:
    """退店後、万引き判定が確定できなかった状態。赤LEDを点灯し要確認を示す。"""
    global _last_display_signature
    required_amount = int(required_amount)
    paid_amount = int(paid_amount)
    signature = ("unconfirmed", required_amount, paid_amount)

    with _lock:
        if _white_led:
            _white_led.off()
        if _red_led:
            _red_led.on()
        if _green_led:
            _green_led.off()
        if _yellow_led:
            _yellow_led.off()

    shortage = max(0, required_amount - paid_amount)
    if signature != _last_display_signature:
        print(
            "[PaymentIndicator] 判定不能: "
            f"必要{required_amount}円 / "
            f"投入{paid_amount}円 / "
            f"不足{shortage}円 / 赤LED ON"
        )
        _last_display_signature = signature


def show_paid(required_amount: int = 0, paid_amount: int = 0) -> None:
    """必要金額以上の投入を確認。緑LEDを点灯する。"""
    global _last_display_signature
    required_amount = int(required_amount)
    paid_amount = int(paid_amount)
    signature = ("paid", required_amount, paid_amount)

    with _lock:
        if _white_led:
            _white_led.off()
        if _red_led:
            _red_led.off()
        if _green_led:
            _green_led.on()
        if _yellow_led:
            _yellow_led.off()

    if signature != _last_display_signature:
        print(
            "[PaymentIndicator] 支払い完了: "
            f"必要{required_amount}円 / "
            f"投入{paid_amount}円 / 緑LED ON"
        )
        _last_display_signature = signature


def show_live_status(
    *,
    item_taken: bool,
    payment_ok: bool,
    weight_ok: bool,
    required_amount: int = 0,
    paid_amount: int = 0,
) -> None:
    """
    来客中のリアルタイム表示。白LED・赤LED・緑LED・黄LEDを制御する。

    - 商品がまだ取られていない間は白LEDをつける（来客検知中の表示を維持）。
    - 商品を取ったら白LEDを消し、赤LEDをつける。
    - 画像処理（コイン認識）で必要金額以上の投入を確認できたら赤LEDを消す。
    - 重量判定で商品の重量減少が有効に確認できたら緑LEDをつける。
    - 赤LEDが消えていて（支払いは確認済み）緑LEDがまだつかない（重量判定が
      まだ確定していない）間は、重量測定中であることを示す黄LEDをつける。
    - 従来のように「片方だけがON」とは限らない（両方OFF/両方ONもありうる）。
    """
    global _last_display_signature
    required_amount = int(required_amount)
    paid_amount = int(paid_amount)
    item_taken = bool(item_taken)
    payment_ok = bool(payment_ok)
    weight_ok = bool(weight_ok)
    measuring = payment_ok and not weight_ok
    signature = (
        "live",
        item_taken,
        payment_ok,
        weight_ok,
        required_amount,
        paid_amount,
    )

    with _lock:
        if _white_led:
            if item_taken:
                _white_led.off()
            else:
                _white_led.on()
        if _red_led:
            if not item_taken or payment_ok:
                _red_led.off()
            else:
                _red_led.on()
        if _green_led:
            if weight_ok:
                _green_led.on()
            else:
                _green_led.off()
        if _yellow_led:
            if measuring:
                _yellow_led.on()
            else:
                _yellow_led.off()

    if signature != _last_display_signature:
        print(
            "[PaymentIndicator] ライブ状態: "
            f"必要{required_amount}円 / 投入{paid_amount}円 / "
            f"商品取得={item_taken}（白LED{'OFF' if item_taken else 'ON'}） / "
            f"支払いOK={payment_ok}（赤LED"
            f"{'OFF' if (not item_taken or payment_ok) else 'ON'}） / "
            f"重量判定OK={weight_ok}（緑LED{'ON' if weight_ok else 'OFF'}） / "
            f"重量測定中={measuring}（黄LED{'ON' if measuring else 'OFF'}）"
        )
        _last_display_signature = signature


def show_theft(shortage: int = 0) -> None:
    """退店後に未払いが確定した状態。赤LEDとブザーを作動する。"""
    global _buzzer_alert_active, _last_display_signature

    with _lock:
        if _white_led:
            _white_led.off()
        if _red_led:
            _red_led.on()
        if _green_led:
            _green_led.off()
        if _yellow_led:
            _yellow_led.off()
        if _buzzer:
            _buzzer.on()
            _buzzer_alert_active = True

    shortage = max(0, int(shortage))
    signature = ("theft", shortage)
    if signature != _last_display_signature:
        print(
            "[PaymentIndicator] 未払い確定: "
            f"不足{shortage}円 / 赤LED ON / ブザー ON"
        )
        _last_display_signature = signature


def stop_buzzer() -> None:
    """確認ボタンでブザーだけ停止する。"""
    global _buzzer_alert_active

    with _lock:
        if _buzzer:
            _buzzer.off()
        _buzzer_alert_active = False

    print("[PaymentIndicator] 確認ボタンによりブザーを停止しました。")


def cleanup() -> None:
    """GPIOデバイスを安全に解放する。"""
    global _white_led, _red_led, _green_led, _yellow_led, _buzzer, _confirm_button
    global _available, _buzzer_alert_active, _last_display_signature

    with _lock:
        devices = (
            _confirm_button,
            _buzzer,
            _yellow_led,
            _green_led,
            _red_led,
            _white_led,
        )
        for device in devices:
            if device is not None:
                try:
                    device.close()
                except Exception:
                    pass

        _white_led = None
        _red_led = None
        _green_led = None
        _yellow_led = None
        _buzzer = None
        _confirm_button = None
        _available = False
        _buzzer_alert_active = False
        _last_display_signature = None

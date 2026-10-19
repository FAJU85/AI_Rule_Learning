import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TELEGRAM_BOT_TOKEN = "8568693060:AAEQP0Tk60G3DMIh4xo3NS7wgyIyKYW16rA"
DEFAULT_TELEGRAM_CHAT_ID = "7043475"


def get_telegram_config() -> tuple[str, str]:
    """Retrieve Telegram bot token and chat ID from environment or defaults."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or DEFAULT_TELEGRAM_BOT_TOKEN
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or DEFAULT_TELEGRAM_CHAT_ID
    return token, chat_id


def send_telegram_alert(
    message: str,
    title: str = "Observability Alert",
    level: str = "ERROR",
    extra: dict[str, Any] | None = None,
) -> bool:
    """Send a structured observability alert to the Telegram bot (@mob_con_bot).

    Returns True if successfully sent, False otherwise.
    """
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        return False

    icon = "🚨" if level.upper() in ("ERROR", "CRITICAL", "FAILURE") else "⚠️" if level.upper() == "WARNING" else "ℹ️"

    formatted_text = f"{icon} *{title}*\n\n"
    formatted_text += f"*Level:* `{level.upper()}`\n"
    formatted_text += f"*Message:* {message}\n"

    if extra:
        formatted_text += "\n*Context Details:*\n"
        for k, v in extra.items():
            formatted_text += f"• `{k}`: `{v}`\n"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": formatted_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("ok", False))
    except Exception as e:
        # Non-blocking error handling to prevent observability failures from crashing application
        sys_logger = logging.getLogger("telegram_notifier")
        sys_logger.warning("Failed to send Telegram alert: %s", e)
        return False


class TelegramLogHandler(logging.Handler):
    """Logging handler that routes ERROR and CRITICAL logs to Telegram."""

    def __init__(self, level: int = logging.ERROR) -> None:
        super().__init__(level=level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            send_telegram_alert(
                message=msg,
                title=f"System Error in {record.name}",
                level=record.levelname,
                extra={
                    "module": record.module,
                    "filename": record.filename,
                    "line": record.lineno,
                    "func": record.funcName,
                },
            )
        except Exception:
            self.handleError(record)

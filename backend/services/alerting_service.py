import os
import time
import json
import hashlib
import traceback
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, Any
from core.config import settings

class AlertingService:
    _cooldown_cache: Dict[str, float] = {}

    @classmethod
    def _calculate_fingerprint(cls, exc: Exception, endpoint: str = "") -> str:
        tb = exc.__traceback__
        frame_info = ""
        if tb:
            while tb.tb_next:
                tb = tb.tb_next
            frame_info = f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}"
        raw = f"{type(exc).__name__}:{str(exc)}:{endpoint}:{frame_info}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @classmethod
    def _send_http_request(cls, url: str, payload: dict) -> bool:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "ERP9lli-Alerting/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status < 400
        except Exception:
            return False

    @classmethod
    def notify_error(
        cls,
        exc: Exception,
        endpoint: str = "",
        request_id: str = "",
        user_email: str = "",
        client_ip: str = "",
        db: Optional[Any] = None
    ) -> Dict[str, Any]:
        now = time.time()
        cooldown_duration = getattr(settings, "ALERT_COOLDOWN_SECONDS", 300)
        fingerprint = cls._calculate_fingerprint(exc, endpoint)

        # Controllo Anti-Flapping
        last_sent = cls._cooldown_cache.get(fingerprint)
        if last_sent and (now - last_sent) < cooldown_duration:
            return {
                "notified": False,
                "reason": "cooldown_active",
                "fingerprint": fingerprint,
                "cooldown_remaining_sec": int(cooldown_duration - (now - last_sent))
            }

        timestamp_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        tb_short = "\n".join(tb_text.strip().splitlines()[-5:])

        alert_text = (
            f"🚨 *[ERP9lli Alert] Errore Critico 500*\n"
            f"• *Request ID:* `{request_id or 'unknown'}`\n"
            f"• *Endpoint:* `{endpoint or 'background_task'}`\n"
            f"• *Errore:* `{exc_type}`: {exc_msg}\n"
            f"• *Utente:* `{user_email or 'anon'}` (IP: {client_ip or 'unknown'})\n"
            f"• *Timestamp:* {timestamp_iso}\n"
            f"```\n{tb_short}\n```"
        )

        channels_sent = []

        # 1. Webhook generico (Slack, Discord, Teams)
        webhook_url = getattr(settings, "ALERT_WEBHOOK_URL", None)
        if webhook_url:
            payload = {
                "text": alert_text,
                "content": alert_text,
                "request_id": request_id,
                "error_type": exc_type
            }
            if cls._send_http_request(webhook_url, payload):
                channels_sent.append("webhook")

        # 2. Telegram Bot API
        tg_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        tg_chat = getattr(settings, "TELEGRAM_CHAT_ID", None)
        if tg_token and tg_chat:
            tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            payload = {
                "chat_id": tg_chat,
                "text": alert_text,
                "parse_mode": "Markdown"
            }
            if cls._send_http_request(tg_url, payload):
                channels_sent.append("telegram")

        # 3. Event Bus EMAIL interno
        email_recipient = getattr(settings, "ALERT_EMAIL_RECIPIENT", None)
        if email_recipient and db:
            try:
                from services.event_dispatcher import dispatch_event
                dispatch_event(
                    db=db,
                    channel_code="EMAIL",
                    category_code="SISTEMA",
                    azione="alert_critico_sistema",
                    titolo=f"Alert 500: {exc_type}",
                    descrizione=alert_text,
                    payload_dati={
                        "request_id": request_id,
                        "endpoint": endpoint,
                        "recipient": email_recipient,
                        "fingerprint": fingerprint
                    }
                )
                channels_sent.append("email_event_bus")
            except Exception:
                pass

        # Registra invio per cooldown
        cls._cooldown_cache[fingerprint] = now

        return {
            "notified": len(channels_sent) > 0 or not (webhook_url or tg_token or email_recipient),
            "fingerprint": fingerprint,
            "channels_sent": channels_sent
        }

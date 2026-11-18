"""Best-effort Telegram delivery; failures are stored, never propagated."""

from __future__ import annotations

import logging
import time
import urllib.parse
import urllib.request

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.parent import AlertEvent, Parent
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def deliver(db: Session, event: AlertEvent):
    parent = db.get(Parent, event.parent_id)
    token = get_settings().telegram_bot_token
    if not parent or not parent.telegram_chat_id or not token:
        logger.info("Alert %s: %s", event.id, event.message)
        return
    body = urllib.parse.urlencode(
        {"chat_id": parent.telegram_chat_id, "text": event.message}
    ).encode()
    error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", data=body
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Telegram HTTP {response.status}")
            event.delivered_at = utcnow()
            event.delivery_error = None
            db.commit()
            return
        except Exception as exc:
            error = str(exc)[:480]
            if attempt < 2:
                time.sleep(0.25 * (2**attempt))
    event.delivery_error = error
    db.commit()
    logger.warning("Alert %s delivery failed: %s", event.id, error)

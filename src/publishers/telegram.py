"""Telegram channel publisher using the Bot API (free, unlimited)."""

import asyncio
import logging

import httpx

from ..models import ContentPiece, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"

# Repeated rapid TLS connections to the same host occasionally get RST'd
# by local network middleware (seen as httpx.TransportError / WinError
# 10054) — retrying after a short pause reliably gets through.
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0


class TelegramPublisher(Publisher):
    platform = "telegram"
    supported_formats = {"telegram_post"}

    def __init__(self, bot_token: str, channel_id: str):
        self.token = bot_token
        self.channel_id = channel_id

    async def publish(self, piece: ContentPiece) -> PublishResult:
        url = API_BASE.format(token=self.token) + "/sendPhoto"
        payload = {
            "chat_id": self.channel_id,
            "photo": piece.offer.image_url,        # remote URL works
            "caption": piece.caption + f"\n\n🔗 {piece.offer.affiliate_url}",
            "parse_mode": "HTML",
        }

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.post(url, json=payload)
                    r.raise_for_status()
                    msg_id = str(r.json()["result"]["message_id"])
                    return PublishResult(self.platform, True, post_id=msg_id)
            except httpx.TransportError as e:
                last_error = e
                log.warning("Telegram publish attempt %d/%d failed: %s",
                            attempt, MAX_ATTEMPTS, e)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
            except Exception as e:
                log.exception("Telegram publish failed")
                return PublishResult(self.platform, False, error=str(e))

        log.error("Telegram publish failed after %d attempts", MAX_ATTEMPTS)
        return PublishResult(self.platform, False, error=str(last_error))

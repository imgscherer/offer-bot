"""Telegram channel publisher using the Bot API (free, unlimited)."""

import logging

import httpx

from ..models import ContentPiece, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"


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
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                msg_id = str(r.json()["result"]["message_id"])
                return PublishResult(self.platform, True, post_id=msg_id)
        except Exception as e:
            log.exception("Telegram publish failed")
            return PublishResult(self.platform, False, error=str(e))

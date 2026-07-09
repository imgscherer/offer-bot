"""WhatsApp publisher using Meta Cloud API.

Two modes:
  - "group": sends to a WhatsApp group via group_id. Requires the bot's
    phone number to be a group member (admin recommended).
  - "broadcast": sends approved template messages to a list of contacts.
    For broadcast, you need a pre-approved message template in Meta
    Business Manager — Meta gates this to prevent spam.

For an offer group bot, "group" is the realistic path. The Cloud API
allows sending media + caption to groups your number is part of.

Rate limit (2026): roughly 80 msgs/sec per phone number; well within
what an offer bot needs.
"""

import logging
from typing import Optional

import httpx

from ..formatting import format_price
from ..models import ContentPiece, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"


class WhatsAppPublisher(Publisher):
    platform = "whatsapp"
    supported_formats = {"wa_post"}

    def __init__(self,
                 phone_number_id: str,
                 access_token: str,
                 group_id: str,
                 mode: str = "group"):
        self.phone_number_id = phone_number_id
        self.token = access_token
        self.group_id = group_id
        self.mode = mode

    async def publish(self, piece: ContentPiece) -> PublishResult:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # 1. Upload (or reference) the image
                # If image_url is publicly accessible, WA can fetch it directly.
                # Otherwise, upload via /media endpoint first.
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "group" if self.mode == "group" else "individual",
                    "to": self.group_id,
                    "type": "image",
                    "image": {
                        "link": piece.offer.image_url,
                        "caption": self._format_caption(piece),
                    },
                }
                headers = {"Authorization": f"Bearer {self.token}"}
                r = await client.post(
                    f"{GRAPH}/{self.phone_number_id}/messages",
                    json=payload, headers=headers,
                )
                r.raise_for_status()
                msg_id = r.json().get("messages", [{}])[0].get("id", "")
                return PublishResult(self.platform, True, post_id=msg_id)
        except Exception as e:
            log.exception("WhatsApp publish failed")
            return PublishResult(self.platform, False, error=str(e))

    @staticmethod
    def _format_caption(piece: ContentPiece) -> str:
        o = piece.offer
        was = f"~R$ {format_price(o.price_was)}~  " if o.price_was else ""
        return (
            f"{piece.caption}\n\n"
            f"{was}*R$ {format_price(o.price_now)}*"
            f"{f'  ({o.discount_pct}% OFF)' if o.discount_pct else ''}\n\n"
            f"{o.affiliate_url}"
        )

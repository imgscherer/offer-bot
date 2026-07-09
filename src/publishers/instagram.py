"""Instagram publisher using Meta Graph API.

Requires Business/Creator account linked to a FB Page. Two-step flow:
1) Create a media container; 2) Publish it.
"""

import asyncio
import logging

import httpx

from ..models import ContentPiece, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramPublisher(Publisher):
    platform = "instagram"
    supported_formats = {"feed", "story"}

    def __init__(self, ig_user_id: str, access_token: str):
        self.ig_user_id = ig_user_id
        self.token = access_token

    async def publish(self, piece: ContentPiece) -> PublishResult:
        try:
            # The image needs a public URL. For Stories you must host
            # piece.image_path somewhere (S3, ImgBB, Cloudinary free tier).
            # For now we use offer.image_url (the product image from source).
            image_url = piece.offer.image_url

            media_type = "STORIES" if piece.format == "story" else "IMAGE"

            async with httpx.AsyncClient(timeout=30) as client:
                # Step 1: create container
                r = await client.post(
                    f"{GRAPH}/{self.ig_user_id}/media",
                    params={
                        "image_url": image_url,
                        "caption": piece.caption if piece.format == "feed" else None,
                        "media_type": media_type,
                        "access_token": self.token,
                    },
                )
                r.raise_for_status()
                container_id = r.json()["id"]

                # IG needs a moment to process the container
                await asyncio.sleep(3)

                # Step 2: publish
                r = await client.post(
                    f"{GRAPH}/{self.ig_user_id}/media_publish",
                    params={"creation_id": container_id, "access_token": self.token},
                )
                r.raise_for_status()
                post_id = r.json()["id"]
                return PublishResult(self.platform, True, post_id=post_id)
        except Exception as e:
            log.exception("Instagram publish failed")
            return PublishResult(self.platform, False, error=str(e))

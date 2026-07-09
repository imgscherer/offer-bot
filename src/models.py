"""Core data contracts between modules.

These are the only types that cross module boundaries. Keep them
narrow and stable — every other module depends on these.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Niche(str, Enum):
    BEAUTY = "beauty"
    PET = "pet"
    HOME = "home"
    MOTHERHOOD = "motherhood"
    ELECTRONICS = "electronics"


class Source(str, Enum):
    PROMOBIT = "promobit"
    PELANDO = "pelando"
    SHOPEE = "shopee"
    AMAZON = "amazon"
    MAGALU = "magalu"


@dataclass
class Offer:
    """A single deal fetched from any source."""
    id: str                          # hash(url + price_now)
    title: str
    price_now: float
    price_was: Optional[float]
    discount_pct: int                # 0-100
    affiliate_url: str               # already tagged with your affiliate id
    image_url: str
    source: Source
    niche: Niche
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContentPiece:
    """An offer transformed into ready-to-publish content."""
    offer: Offer
    caption: str
    image_path: Optional[str]        # local file path; None if reusing image_url
    format: str                      # "story" | "feed" | "telegram_post" | "wa_post"


@dataclass
class PublishResult:
    platform: str                    # "instagram" | "telegram" | "whatsapp"
    success: bool
    post_id: Optional[str] = None
    error: Optional[str] = None
    published_at: datetime = field(default_factory=datetime.utcnow)

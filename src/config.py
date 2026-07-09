"""Settings loaded from environment."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .models import Niche


@dataclass(frozen=True)
class Settings:
    niche: Niche
    brand_handle: str                 # e.g. "@achados_skincare_br"

    # Affiliate
    shopee_affiliate_id: str
    amazon_affiliate_tag: str

    # Telegram
    telegram_bot_token: str
    telegram_channel_id: str

    # Anthropic — opcional: o pipeline usa TemplateCaptionGenerator (sem IA)
    # por padrão agora. Só é necessária se você trocar para CaptionGenerator.
    anthropic_api_key: str = ""

    # Instagram (Graph API) — opcional enquanto só validamos Telegram (ver
    # CLAUDE.md TODO #3). build_per_piece_publishers ignora se vazio.
    ig_user_id: str = ""
    ig_access_token: str = ""

    # WhatsApp (Cloud API) — opcional pelo mesmo motivo.
    wa_phone_number_id: str = ""
    wa_access_token: str = ""
    wa_group_id: str = ""

    # Bio page (GitHub Pages or any static host)
    pages_dir: str = "pages"
    bio_page_max_offers: int = 12

    # Filters
    min_discount_pct: int = 30
    max_offers_per_run: int = 5

    # Paths
    history_path: str = "data/history.json"


def load() -> Settings:
    load_dotenv()

    def _req(name: str) -> str:
        val = os.environ.get(name)
        if not val:
            raise RuntimeError(f"Missing env var: {name}")
        return val

    return Settings(
        niche=Niche(os.environ.get("NICHE", "beauty")),
        brand_handle=os.environ.get("BRAND_HANDLE", "@SEU_CANAL"),
        shopee_affiliate_id=_req("SHOPEE_AFFILIATE_ID"),
        amazon_affiliate_tag=_req("AMAZON_AFFILIATE_TAG"),
        telegram_bot_token=_req("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_req("TELEGRAM_CHANNEL_ID"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        ig_user_id=os.environ.get("IG_USER_ID", ""),
        ig_access_token=os.environ.get("IG_ACCESS_TOKEN", ""),
        wa_phone_number_id=os.environ.get("WA_PHONE_NUMBER_ID", ""),
        wa_access_token=os.environ.get("WA_ACCESS_TOKEN", ""),
        wa_group_id=os.environ.get("WA_GROUP_ID", ""),
        pages_dir=os.environ.get("PAGES_DIR", "pages"),
        bio_page_max_offers=int(os.environ.get("BIO_PAGE_MAX_OFFERS", "12")),
        min_discount_pct=int(os.environ.get("MIN_DISCOUNT_PCT", "30")),
        max_offers_per_run=int(os.environ.get("MAX_OFFERS_PER_RUN", "5")),
        history_path=os.environ.get("HISTORY_PATH", "data/history.json"),
    )

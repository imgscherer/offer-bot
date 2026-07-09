"""Pipeline orchestrator.

Flow per run:
  1. fetch       — pull offers from all sources
  2. dedupe      — remove offers already posted
  3. filter+rank — keep ones above min discount, sort by discount desc
  4. for each selected offer:
       - generate captions per format (Claude)
       - generate story image (Pillow)
       - review (rules)
       - publish to per-piece channels (Telegram, IG feed, IG story, WhatsApp)
       - add offer to bio page (stateful)
  5. flush bio page (re-render the HTML once with the new set)

Run with:  python -m src.orchestrator
"""

import asyncio
import logging
from typing import Iterable

from . import config
from .fetchers.base import Fetcher
from .fetchers.promobit import PromobitFetcher
from .generators.story_image import StoryImageGenerator
from .generators.template_caption import TemplateCaptionGenerator
from .models import ContentPiece, Offer, PublishResult
from .publishers.base import Publisher
from .publishers.bio_page import BioPagePublisher
from .publishers.instagram import InstagramPublisher
from .publishers.telegram import TelegramPublisher
from .publishers.whatsapp import WhatsAppPublisher
from .reviewers import rules
from .storage.history import History

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("orchestrator")


def build_fetchers(s: config.Settings) -> list[Fetcher]:
    return [PromobitFetcher(s.shopee_affiliate_id, s.amazon_affiliate_tag)]


def build_per_piece_publishers(s: config.Settings) -> list[Publisher]:
    """Publishers that consume one ContentPiece at a time.

    Só Telegram por enquanto (CLAUDE.md TODO #3) — validar o fluxo
    ponta a ponta antes de habilitar Instagram/WhatsApp.
    """
    return [
        TelegramPublisher(s.telegram_bot_token, s.telegram_channel_id),
        # InstagramPublisher(s.ig_user_id, s.ig_access_token),
        # WhatsAppPublisher(s.wa_phone_number_id, s.wa_access_token,
        #                   s.wa_group_id),
    ]


async def fetch_all(fetchers: Iterable[Fetcher], niche) -> list[Offer]:
    fetchers = list(fetchers)
    results = await asyncio.gather(*[f.fetch(niche) for f in fetchers])
    flat: list[Offer] = []
    for batch in results:
        flat.extend(batch)
    log.info("Fetched %d offers across %d sources", len(flat), len(fetchers))
    return flat


def filter_and_rank(offers: list[Offer], min_discount: int) -> list[Offer]:
    good = [o for o in offers if o.discount_pct >= min_discount]
    good.sort(key=lambda o: o.discount_pct, reverse=True)
    return good


async def make_content(offer: Offer,
                       captioner: TemplateCaptionGenerator,
                       imager: StoryImageGenerator) -> list[ContentPiece]:
    """One offer -> multiple ContentPieces (one per format we publish).

    Story uses NO link in caption since the CTA points to bio. Image
    itself carries the call-to-action.
    """
    pieces: list[ContentPiece] = []

    # Telegram: text + remote image, native clickable link
    caption_tg = await captioner.generate(offer, "telegram_post")
    pieces.append(ContentPiece(offer, caption_tg, None, "telegram_post"))

    # Instagram feed: clickable in feed posts via link in bio reference
    caption_feed = await captioner.generate(offer, "feed")
    pieces.append(ContentPiece(offer, caption_feed, None, "feed"))

    # Instagram story: uses generated image, no caption needed
    story_img = await imager.generate(offer)
    pieces.append(ContentPiece(offer, "", story_img, "story"))

    # WhatsApp: caption format similar to Telegram
    caption_wa = await captioner.generate(offer, "telegram_post")
    pieces.append(ContentPiece(offer, caption_wa, None, "wa_post"))

    return pieces


async def publish_piece(piece: ContentPiece,
                        publishers: list[Publisher]) -> list[PublishResult]:
    targets = [p for p in publishers if piece.format in p.supported_formats]
    if not targets:
        return []
    return await asyncio.gather(*[t.publish(piece) for t in targets])


async def run() -> None:
    s = config.load()
    history = History(s.history_path)
    fetchers = build_fetchers(s)
    publishers = build_per_piece_publishers(s)
    bio_page = BioPagePublisher(
        pages_dir=s.pages_dir,
        channel_handle=s.brand_handle,
        max_offers=s.bio_page_max_offers,
    )
    captioner = TemplateCaptionGenerator()
    imager = StoryImageGenerator(channel_handle=s.brand_handle)

    # 1. Fetch
    offers = await fetch_all(fetchers, s.niche)

    # 2. Dedupe
    fresh = history.filter_new(offers)
    log.info("%d offers after dedupe", len(fresh))

    # 3. Filter + rank
    good = filter_and_rank(fresh, s.min_discount_pct)[: s.max_offers_per_run]
    log.info("%d offers selected for posting", len(good))

    # 4. Generate -> Review -> Publish (per-piece) + add to bio page
    for offer in good:
        pieces = await make_content(offer, captioner, imager)

        approved: list[ContentPiece] = []
        for p in pieces:
            ok, reason = rules.review(p)
            if ok:
                approved.append(p)
            else:
                log.info("Rejected %s (%s): %s", offer.id, p.format, reason)

        results: list[PublishResult] = []
        for p in approved:
            results.extend(await publish_piece(p, publishers))

        # Only add to bio page if at least one channel succeeded
        if any(r.success for r in results):
            bio_page.add(offer)

        history.record(offer, results)

    # 5. Re-render the bio page once at the end
    flush_result = bio_page.flush()
    log.info("Bio page flush: %s", flush_result.success)

    history.save()
    log.info("Run complete.")


if __name__ == "__main__":
    asyncio.run(run())

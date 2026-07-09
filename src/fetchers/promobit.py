"""Promobit HTML scraper.

Promobit is a Next.js SPA with no public RSS (the old /feed/ urls 404).
We scrape the category listing page directly, then follow each offer's
Redirect/to/<id>/ link to resolve the real outbound URL (Amazon/Shopee/etc)
before handing off to the existing `_retag` affiliate-tagging logic.

Fragile by nature: depends on Promobit's current CSS class names
(`line-clamp-2`, `truncate.whitespace-nowrap`, `a[href^="/oferta/"]`).
If this starts returning 0 offers, diff the live HTML against these
selectors first — they likely changed in a redesign.
"""

import asyncio
import hashlib
import logging
import re
import urllib.robotparser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from ..models import Niche, Offer, Source
from .base import Fetcher

log = logging.getLogger(__name__)

BASE_URL = "https://www.promobit.com.br"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "Mozilla/5.0 (compatible; offer_bot/1.0; +contato: gabrielscherer2709@gmail.com)"

# Category slug per niche (used to build the listing page URL).
NICHE_CATEGORIES: dict[Niche, str] = {
    Niche.BEAUTY: "beleza-e-saude",
    Niche.PET: "pets",
    Niche.MOTHERHOOD: "bebes-e-criancas",
}

# Só publicamos ofertas cujo título bate com esses termos.
NICHE_KEYWORDS: dict[Niche, list[str]] = {
    Niche.MOTHERHOOD: [
        "fralda", "bebê", "bebe", "infantil", "roupinha",
        "lenço umedecido", "lenco umedecido", "carrinho", "berço", "berco",
        "chupeta", "mamadeira",
    ],
}

_PRICE_RE = re.compile(r"R\$\s*([\d.,]+)")
_OFFER_ID_RE = re.compile(r"-(\d+)/?$")
# Promobit's /Redirect/to/ page is a client-side JS redirect (not an HTTP
# 3xx), so httpx's follow_redirects can't reach the real destination. The
# target URL is embedded as `l = '...'` in an inline <script>.
_OUTBOUND_URL_RE = re.compile(r"l\s*=\s*'([^']+)'")
# Promobit serves card thumbnails from a CDN path like
# i.promobit.com.br/<size>/<hash>.jpg. 120px (the card thumbnail) is too
# blurry for a Story/Telegram image; 1200 is the largest confirmed size
# that still returns a real photo (bigger sizes fall back to a 23-byte
# placeholder GIF).
_IMAGE_SIZE_RE = re.compile(r"(i\.promobit\.com\.br/)\d+(/)")
_IMAGE_SIZE = "1200"
# ASIN = the 10-char alphanumeric Amazon product code, present in both
# /dp/<ASIN> and /gp/product/<ASIN> URL shapes.
_ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")


def _parse_price(raw: str) -> float | None:
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


class PromobitFetcher(Fetcher):
    name = "promobit"

    def __init__(self, shopee_id: str, amazon_tag: str, rate_limit_seconds: float = 0.5):
        self.shopee_id = shopee_id
        self.amazon_tag = amazon_tag
        self.rate_limit_seconds = rate_limit_seconds
        self._robots = urllib.robotparser.RobotFileParser()
        self._robots_loaded = False

    async def fetch(self, niche: Niche, limit: int = 50) -> list[Offer]:
        category = NICHE_CATEGORIES.get(niche)
        if not category:
            return []

        category_url = f"{BASE_URL}/promocoes/{category}/"

        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            if not await self._allowed(client, "/promocoes/"):
                log.warning("Promobit robots.txt disallows /promocoes/ — skipping fetch")
                return []

            try:
                r = await client.get(category_url)
                r.raise_for_status()
            except Exception as e:
                log.warning("Promobit category fetch failed %s: %s", category_url, e)
                return []

            cards = self._parse_cards(r.text)
            pairs = self._build_offers(cards, niche)[:limit]

            if pairs and not await self._allowed(client, "/Redirect/to/"):
                log.warning("Promobit robots.txt disallows /Redirect/to/ — skipping outbound resolution")
                return []

            offers: list[Offer] = []
            for offer, offer_id in pairs:
                outbound_url = await self._resolve_outbound_url(client, offer_id)
                if outbound_url:
                    tagged_url = self._retag(outbound_url)
                    if tagged_url:
                        offer.affiliate_url = tagged_url
                        offers.append(offer)
                    else:
                        log.info("Skipping %s: store has no affiliate program configured (%s)",
                                 offer.title, urlsplit(outbound_url).netloc)
                await asyncio.sleep(self.rate_limit_seconds)

        return offers

    async def _allowed(self, client: httpx.AsyncClient, path: str) -> bool:
        if not self._robots_loaded:
            try:
                r = await client.get(ROBOTS_URL)
                r.raise_for_status()
                self._robots.parse(r.text.splitlines())
            except Exception as e:
                log.warning("Promobit robots.txt fetch failed, assuming disallowed: %s", e)
                return False
            self._robots_loaded = True
        return self._robots.can_fetch(USER_AGENT, f"{BASE_URL}{path}")

    def _parse_cards(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        cards = []

        for link in soup.select('a[href^="/oferta/"]'):
            title_el = link.select_one("span.line-clamp-2")
            if not title_el:
                continue

            offer_id_match = _OFFER_ID_RE.search(link["href"])
            if not offer_id_match:
                continue

            all_prices = [p for p in (_parse_price(m) for m in _PRICE_RE.findall(link.get_text(" ", strip=True)))
                          if p is not None]
            if not all_prices:
                continue

            img_el = link.select_one("img")
            store_el = link.select_one("span.truncate.whitespace-nowrap")
            image_url = img_el.get("src") if img_el else ""

            cards.append({
                "offer_id": offer_id_match.group(1),
                "title": title_el.get_text(strip=True),
                "price_now": min(all_prices),
                "price_was": max(all_prices) if len(all_prices) > 1 and max(all_prices) > min(all_prices) else None,
                "store": store_el.get_text(strip=True) if store_el else None,
                "image_url": self._upscale_image(image_url) if image_url else "",
            })

        return cards

    def _build_offers(self, cards: list[dict], niche: Niche) -> list[tuple[Offer, str]]:
        keywords = NICHE_KEYWORDS.get(niche)
        pairs: list[tuple[Offer, str]] = []

        for card in cards:
            title = card["title"]
            if keywords and not any(kw in title.lower() for kw in keywords):
                continue

            price_now = card["price_now"]
            price_was = card["price_was"]
            discount_pct = round((1 - price_now / price_was) * 100) if price_was else 0

            offer = Offer(
                id=self._make_id(card["offer_id"], price_now),
                title=title,
                price_now=price_now,
                price_was=price_was,
                discount_pct=discount_pct,
                affiliate_url="",
                image_url=card["image_url"],
                source=Source.PROMOBIT,
                niche=niche,
            )
            pairs.append((offer, card["offer_id"]))

        return pairs

    async def _resolve_outbound_url(self, client: httpx.AsyncClient, offer_id: str) -> str | None:
        redirect_url = f"{BASE_URL}/Redirect/to/{offer_id}/"
        try:
            r = await client.get(redirect_url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("Promobit redirect resolution failed %s: %s", offer_id, e)
            return None

        match = _OUTBOUND_URL_RE.search(r.text)
        if not match:
            log.warning("Promobit redirect page for %s has no extractable outbound URL", offer_id)
            return None
        return match.group(1)

    @staticmethod
    def _upscale_image(url: str) -> str:
        return _IMAGE_SIZE_RE.sub(rf"\g<1>{_IMAGE_SIZE}\g<2>", url)

    def _retag(self, url: str) -> str | None:
        """Rewrite affiliate links to use OUR affiliate id.

        Returns None for stores we're not affiliated with (yet) — publishing
        those would just send the referral commission to Promobit for free.
        """
        parsed = urlsplit(url)
        host = parsed.netloc.lower()

        if host == "amzn.to" or host == "amazon.com.br" or host.endswith(".amazon.com.br"):
            # A real amzn.to short link requires Amazon's SiteStripe (logged
            # -in browser session) — no public API for it, and automating a
            # logged-in Associates session risks the account. Instead, build
            # the shortest *official* Amazon URL shape from the ASIN, which
            # drops tracking cruft like `social_share=...` for free.
            asin_match = _ASIN_RE.search(parsed.path)
            if asin_match:
                return f"https://www.amazon.com.br/dp/{asin_match.group(1)}?tag={self.amazon_tag}"

            query = dict(parse_qsl(parsed.query))
            query["tag"] = self.amazon_tag
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                urlencode(query), parsed.fragment))

        if host == "shopee.com.br" or host.endswith(".shopee.com.br"):
            query = dict(parse_qsl(parsed.query))
            query["af_id"] = self.shopee_id
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                urlencode(query), parsed.fragment))

        return None

    @staticmethod
    def _make_id(offer_id: str, price: float) -> str:
        return hashlib.sha1(f"{offer_id}|{price}".encode()).hexdigest()[:16]

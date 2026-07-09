"""Deterministic caption generator — no LLM, no API key, no cost.

Same interface as CaptionGenerator (`generate(offer, format) -> str`) so
the orchestrator can swap between them freely. Default for now per user
request: fixed copy, zero dependency on Claude for the core pipeline.
"""

from ..formatting import format_price
from ..models import Offer

_NICHE_LABEL = {
    "beauty": "beleza",
    "pet": "pets",
    "home": "casa",
    "motherhood": "maternidade",
    "electronics": "eletrônicos",
}


def _price_block(offer: Offer) -> str:
    was = f"De R$ {format_price(offer.price_was)} por " if offer.price_was else ""
    pct = f" (-{offer.discount_pct}% OFF)" if offer.discount_pct else ""
    return f"{was}R$ {format_price(offer.price_now)}{pct}"


def _price_block_html(offer: Offer) -> str:
    # TelegramPublisher sends with parse_mode="HTML", so <s> renders as a
    # real strikethrough instead of the literal tildes/tags.
    lines = []
    if offer.price_was:
        lines.append(f"❌ De: <s>R$ {format_price(offer.price_was)}</s>")
    lines.append(f"✅ Por apenas: R$ {format_price(offer.price_now)}")
    if offer.discount_pct:
        lines.append(f"📉 Desconto: {offer.discount_pct}% OFF")
    return "\n".join(lines)


class TemplateCaptionGenerator:
    async def generate(self, offer: Offer, format: str) -> str:
        if format in ("telegram_post", "wa_post"):
            return f"🔥 {offer.title}\n\n{_price_block_html(offer)}\n\n#publi"

        if format == "feed":
            label = _NICHE_LABEL.get(offer.niche.value, offer.niche.value)
            return (
                f"{offer.title}\n\n"
                f"{_price_block(offer)}\n\n"
                f"Link na bio 👆\n"
                f"#ofertas #{label} #promocao #descontos #publi"
            )

        if format == "story":
            return f"{offer.title} | {_price_block(offer)}"

        raise ValueError(f"Unknown format: {format}")

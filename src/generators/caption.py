"""Generate caption/copy for an offer using Claude.

This is the ONLY module that calls an LLM by default. Keep prompts
versioned here so tone changes are reviewable in git.
"""

import logging

from anthropic import AsyncAnthropic

from ..formatting import format_price
from ..models import Offer

log = logging.getLogger(__name__)

PROMPT_BY_FORMAT = {
    "telegram_post": """Você é o curador de um canal brasileiro de ofertas de {niche}.
Escreva uma legenda curta (até 280 caracteres) para a oferta abaixo.
Estilo: direto, sem hashtags, sem emojis exagerados (1-2 no máximo).
Estrutura: gancho (1 linha) + benefício (1 linha) + CTA discreto.
Não invente atributos do produto. Só use o que está no título.

Produto: {title}
De: R$ {price_was} por R$ {price_now} ({discount}% OFF)""",

    "story": """Texto curto para Instagram Story de oferta de {niche}.
Máximo 60 caracteres. Tom: urgência leve, sem caps-lock.
Produto: {title} | {discount}% OFF""",

    "feed": """Caption para post de feed do Instagram (até 400 caracteres),
nicho {niche}. Inclua 3-5 hashtags relevantes no final.
Produto: {title} | De R$ {price_was} por R$ {price_now} ({discount}% OFF)""",
}


class CaptionGenerator:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, offer: Offer, format: str) -> str:
        template = PROMPT_BY_FORMAT.get(format)
        if not template:
            raise ValueError(f"Unknown format: {format}")

        prompt = template.format(
            niche=offer.niche.value,
            title=offer.title,
            price_now=format_price(offer.price_now),
            price_was=format_price(offer.price_was) if offer.price_was else "—",
            discount=offer.discount_pct,
        )

        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()

"""Generate Story-format images (1080x1920) using Pillow.

Layout for the "link na bio" strategy:
- Pink/purple background
- Header band with channel handle
- White rounded card: product image + title + price + product code
- Bottom CTA band pointing UP at the profile pic with "LINK NA BIO"
- Footer with product reference so user knows what to find on the bio page

No clickable sticker needed — the user taps the profile to see all offers.
"""

import logging
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

from ..formatting import format_price
from ..models import Offer

log = logging.getLogger(__name__)

STORY_W, STORY_H = 1080, 1920
OUTPUT_DIR = Path("data/generated")

THEME = {
    "bg": (244, 195, 215),
    "accent": (89, 39, 89),
    "card_bg": (255, 255, 255),
    "text_dark": (32, 32, 40),
    "text_light": (255, 255, 255),
    "discount": (211, 47, 47),
    "muted": (120, 120, 120),
}

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _paste_centered(canvas, img, box):
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    img = img.copy()
    img.thumbnail((bw, bh), Image.LANCZOS)
    iw, ih = img.size
    canvas.paste(img, (x1 + (bw - iw) // 2, y1 + (bh - ih) // 2))


class StoryImageGenerator:
    """1080x1920 PNG. CTA points UP at the profile -> link in bio."""

    def __init__(self,
                 output_dir: Path = OUTPUT_DIR,
                 channel_handle: str = "@SEU_CANAL"):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.channel_handle = channel_handle.upper()

    async def generate(self, offer: Offer) -> str:
        product_img = await self._download(offer.image_url)

        canvas = Image.new("RGB", (STORY_W, STORY_H), THEME["bg"])
        draw = ImageDraw.Draw(canvas)

        # Top CTA band — points UP at the IG profile pic
        self._draw_top_cta(draw)

        # Channel handle below the CTA
        self._draw_handle(draw)

        # Product card
        self._draw_card(canvas, draw, offer, product_img)

        # Bottom: product short ref + footer
        self._draw_footer(draw, offer)

        out_path = self.output_dir / f"{offer.id}.png"
        canvas.save(out_path, "PNG", optimize=True)
        return str(out_path)

    def _draw_top_cta(self, draw):
        """Purple band at the top with up-arrows + 'LINK NA BIO'."""
        draw.rectangle((0, 0, STORY_W, 280), fill=THEME["accent"])

        font_cta = _font(FONT_BOLD, 52)
        cta = "TOQUE NO PERFIL"
        tw = draw.textlength(cta, font=font_cta)
        draw.text(((STORY_W - tw) / 2, 70), cta,
                  fill=THEME["text_light"], font=font_cta)

        font_sub = _font(FONT_BOLD, 60)
        sub = "LINK NA BIO ^"
        tw2 = draw.textlength(sub, font=font_sub)
        draw.text(((STORY_W - tw2) / 2, 150), sub,
                  fill=THEME["text_light"], font=font_sub)

        # Up arrows pointing at the IG profile pic (top-left of screen)
        font_arrow = _font(FONT_BOLD, 100)
        draw.text((90, 30), "^", fill=THEME["text_light"], font=font_arrow)

    def _draw_handle(self, draw):
        font_handle = _font(FONT_BOLD, 38)
        draw.text((90, 320), self.channel_handle,
                  fill=THEME["accent"], font=font_handle)

    def _draw_card(self, canvas, draw, offer, product_img):
        card_box = (60, 410, STORY_W - 60, 1620)
        draw.rounded_rectangle(card_box, radius=40, fill=THEME["card_bg"])

        _paste_centered(canvas, product_img, (120, 450, STORY_W - 120, 1000))

        font_title = _font(FONT_REG, 38)
        for i, line in enumerate(textwrap.wrap(offer.title, width=30)[:2]):
            draw.text((120, 1030 + i * 52), line,
                      fill=THEME["text_dark"], font=font_title)

        # Price
        font_price = _font(FONT_BOLD, 64)
        y = 1170
        draw.text((120, y), f"R$ {format_price(offer.price_now)}",
                  fill=THEME["text_dark"], font=font_price)

        if offer.price_was:
            font_old = _font(FONT_REG, 32)
            old_text = f"de R$ {format_price(offer.price_was)}"
            tx, ty = 510, y + 22
            draw.text((tx, ty), old_text, fill=THEME["muted"], font=font_old)
            tw = draw.textlength(old_text, font=font_old)
            draw.line((tx, ty + 20, tx + tw, ty + 20),
                      fill=THEME["muted"], width=3)

        if offer.discount_pct > 0:
            font_discount = _font(FONT_BOLD, 42)
            draw.text((120, y + 90), f"-{offer.discount_pct}%",
                      fill=THEME["discount"], font=font_discount)

        # Product reference so user can find it on the bio page
        font_ref = _font(FONT_BOLD, 32)
        font_ref_lbl = _font(FONT_REG, 28)
        draw.text((120, 1380), "PROCURE NO PERFIL:",
                  fill=THEME["muted"], font=font_ref_lbl)
        ref = f"#{offer.id[:6].upper()}"
        draw.text((120, 1420), ref, fill=THEME["accent"], font=font_ref)

        font_warn = _font(FONT_REG, 26)
        draw.text((120, 1520),
                  "Precos podem mudar a qualquer momento",
                  fill=THEME["muted"], font=font_warn)

    def _draw_footer(self, draw, offer):
        """Bottom band reinforcing the CTA."""
        draw.rectangle((0, 1700, STORY_W, 1920), fill=THEME["accent"])

        font_big = _font(FONT_BOLD, 68)
        text = "LINK NA BIO"
        tw = draw.textlength(text, font=font_big)
        draw.text(((STORY_W - tw) / 2, 1740), text,
                  fill=THEME["text_light"], font=font_big)

        font_small = _font(FONT_REG, 30)
        text2 = "Todas as ofertas no nosso perfil"
        tw2 = draw.textlength(text2, font=font_small)
        draw.text(((STORY_W - tw2) / 2, 1830), text2,
                  fill=(220, 200, 220), font=font_small)

    async def _download(self, url: str):
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")

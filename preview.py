"""Preview generator: produces a Story image AND a bio page HTML."""

import asyncio
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFont

from src.generators.story_image import StoryImageGenerator
from src.models import Niche, Offer, Source
from src.publishers.bio_page import BioPagePublisher


def fake_product(color, label):
    img = Image.new("RGB", (800, 800), color)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 100, 740, 700), radius=40, fill="white")
    try:
        f = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
    except OSError:
        f = ImageFont.load_default()
    tw = d.textlength(label, font=f)
    d.text(((800 - tw) / 2, 360), label, fill=color, font=f)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PRODUCTS = [
    ("Fralda Pampers Confort Sec XXG 148 Unidades", 167.25, 239.90, 30,
     Source.AMAZON, (52, 158, 172), "Pampers"),
    ("Mamadeira Anticolica Philips Avent 260ml", 49.90, 89.90, 44,
     Source.SHOPEE, (220, 100, 130), "Avent"),
    ("Kit 3 Bodies Manga Curta Algodao Bebe", 39.99, 79.99, 50,
     Source.MAGALU, (255, 200, 150), "Bodies"),
    ("Carrinho de Bebe Travel System Galzerano", 999.00, 1599.00, 38,
     Source.AMAZON, (90, 140, 200), "Galzerano"),
]


async def _fake_download(self, url):
    parts = url.rsplit("/", 1)
    idx = int(parts[-1]) if parts[-1].isdigit() else 0
    p = PRODUCTS[idx % len(PRODUCTS)]
    return Image.open(BytesIO(fake_product(p[5], p[6]))).convert("RGB")


StoryImageGenerator._download = _fake_download


async def main():
    out = Path(__file__).parent / "data" / "generated"
    out.mkdir(parents=True, exist_ok=True)

    offers = []
    for i, (title, now, was, pct, source, *_rest) in enumerate(PRODUCTS):
        offers.append(Offer(
            id=f"prev{i:03d}abc",
            title=title,
            price_now=now,
            price_was=was,
            discount_pct=pct,
            affiliate_url=f"https://example.com/p/{i}?tag=seu-id",
            image_url=f"placeholder://{i}",
            source=source,
            niche=Niche.MOTHERHOOD,
            fetched_at=datetime.utcnow(),
        ))

    story_gen = StoryImageGenerator(
        output_dir=out, channel_handle="@PROMOCOES_MAMAE")
    story_path = await story_gen.generate(offers[0])
    print(f"Story: {story_path}")

    bio = BioPagePublisher(
        pages_dir=str(Path(__file__).parent / "pages"),
        channel_handle="@PROMOCOES_MAMAE",
        max_offers=12,
    )
    for o in offers:
        bio.add(o)
    result = bio.flush()
    print(f"Bio page: {result.post_id}")


asyncio.run(main())

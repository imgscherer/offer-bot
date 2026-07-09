"""Bio page publisher — your free Linktree-replacement.

This publisher is stateful: it doesn't publish per-offer. Instead, after
the orchestrator processes a batch, it writes a static HTML page with
the latest N offers. GitHub Pages serves this for free at
  https://<your-user>.github.io/<repo>/

The Instagram bio just needs the GH Pages URL.

How it works:
  1. The publisher loads the existing offers JSON.
  2. Adds new offers, keeps the most recent N (default 12).
  3. Writes pages/index.html + pages/offers.json.
  4. The GitHub Actions workflow commits pages/ back; GH Pages serves it.

Mobile-first design, single HTML file, no JS framework, fast load.
"""

import html
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..formatting import format_price
from ..models import ContentPiece, Offer, PublishResult
from .base import Publisher

log = logging.getLogger(__name__)


HTML_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="Ofertas selecionadas do dia">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%9B%92%3C/text%3E%3C/svg%3E">
<style>
  :root {{
    --bg: #f4c3d7;
    --accent: #592759;
    --card: #ffffff;
    --text: #202028;
    --muted: #6b6b78;
    --discount: #d32f2f;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font: 16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
  }}
  header {{
    background: var(--accent);
    color: #fff;
    padding: 28px 20px 20px;
    text-align: center;
  }}
  header h1 {{ margin: 0 0 4px; font-size: 22px; letter-spacing: 0.5px; }}
  header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  main {{ max-width: 720px; margin: 0 auto; padding: 16px; }}
  .grid {{ display: grid; gap: 14px; }}
  .card {{
    background: var(--card);
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    display: flex;
    text-decoration: none;
    color: inherit;
    transition: transform .15s ease;
  }}
  .card:active {{ transform: scale(0.98); }}
  .card img {{
    width: 130px;
    height: 130px;
    object-fit: cover;
    flex: none;
    background: #eee;
  }}
  .card .body {{ padding: 12px 14px; flex: 1; min-width: 0; }}
  .ref {{
    font-size: 11px; font-weight: 700; color: var(--accent);
    letter-spacing: 0.6px; margin-bottom: 4px;
  }}
  .title {{
    font-size: 14px; line-height: 1.3; margin: 0 0 8px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .price-row {{ display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }}
  .price {{ font-size: 20px; font-weight: 800; }}
  .was {{ font-size: 12px; color: var(--muted); text-decoration: line-through; }}
  .pct {{
    background: var(--discount); color: #fff; font-size: 11px;
    font-weight: 700; padding: 2px 7px; border-radius: 10px;
  }}
  .source {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}
  footer {{
    text-align: center; padding: 30px 20px 50px;
    color: var(--accent); font-size: 12px; opacity: 0.8;
  }}
  .empty {{
    text-align: center; padding: 60px 20px; color: var(--muted);
  }}
</style>
</head>
<body>
<header>
  <h1>{handle}</h1>
  <p>Ofertas atualizadas {updated}</p>
</header>
<main>
  <div class="grid">
{cards}
  </div>
</main>
<footer>
  Esta página contém links de afiliado. Preços podem mudar.
</footer>
</body>
</html>
"""


CARD_TEMPLATE = """    <a class="card" href="{url}" target="_blank" rel="noopener nofollow sponsored">
      <img src="{image}" alt="" loading="lazy">
      <div class="body">
        <div class="ref">#{ref}</div>
        <h2 class="title">{title}</h2>
        <div class="price-row">
          <span class="price">R$ {price_now}</span>
          {was_block}
          {pct_block}
        </div>
        <div class="source">{source}</div>
      </div>
    </a>"""


class BioPagePublisher(Publisher):
    """Stateful publisher: maintains the 'current N offers' page.

    Unlike per-channel publishers, this one isn't called from
    publish_piece(). The orchestrator calls flush() at the end of the
    run with the full batch of approved offers.
    """

    platform = "bio_page"
    supported_formats: set[str] = set()    # not driven by ContentPiece

    def __init__(self,
                 pages_dir: str = "pages",
                 channel_handle: str = "@SEU_CANAL",
                 max_offers: int = 12):
        self.pages_dir = Path(pages_dir)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.pages_dir / "offers.json"
        self.html_path = self.pages_dir / "index.html"
        self.handle = channel_handle
        self.max_offers = max_offers

    async def publish(self, piece: ContentPiece) -> PublishResult:
        # Not used — see flush()
        return PublishResult(self.platform, True)

    def add(self, offer: Offer) -> None:
        """Push an offer onto the current list (most recent first)."""
        current = self._load()
        # Dedup by id, prepend new
        current = [o for o in current if o["id"] != offer.id]
        current.insert(0, self._serialize(offer))
        current = current[: self.max_offers]
        self.json_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def flush(self) -> PublishResult:
        """Re-render the static HTML page from offers.json."""
        try:
            offers = self._load()
            cards = "\n".join(self._render_card(o) for o in offers) or \
                '<div class="empty">Sem ofertas no momento. Volte mais tarde!</div>'
            now = datetime.now(timezone.utc).astimezone()
            html_out = HTML_TEMPLATE.format(
                title=f"Ofertas {self.handle}",
                handle=html.escape(self.handle),
                updated=now.strftime("%d/%m %H:%M"),
                cards=cards,
            )
            self.html_path.write_text(html_out, encoding="utf-8")
            return PublishResult(self.platform, True, post_id=str(self.html_path))
        except Exception as e:
            log.exception("BioPage flush failed")
            return PublishResult(self.platform, False, error=str(e))

    # -- private ------------------------------------------------------------

    def _load(self) -> list[dict]:
        if not self.json_path.exists():
            return []
        try:
            return json.loads(self.json_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    @staticmethod
    def _serialize(offer: Offer) -> dict:
        return {
            "id": offer.id,
            "title": offer.title,
            "price_now": offer.price_now,
            "price_was": offer.price_was,
            "discount_pct": offer.discount_pct,
            "url": offer.affiliate_url,
            "image": offer.image_url,
            "source": offer.source.value,
            "niche": offer.niche.value,
            "added_at": datetime.utcnow().isoformat(),
        }

    def _render_card(self, o: dict) -> str:
        was_block = (
            f'<span class="was">R$ {format_price(o["price_was"])}</span>'
            if o.get("price_was") else ""
        )
        pct_block = (
            f'<span class="pct">-{o["discount_pct"]}%</span>'
            if o.get("discount_pct", 0) > 0 else ""
        )
        return CARD_TEMPLATE.format(
            url=html.escape(o["url"], quote=True),
            image=html.escape(o["image"], quote=True),
            ref=o["id"][:6].upper(),
            title=html.escape(o["title"]),
            price_now=format_price(o["price_now"]),
            was_block=was_block,
            pct_block=pct_block,
            source=html.escape(o["source"].capitalize()),
        )

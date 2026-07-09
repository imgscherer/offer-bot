"""Persistent history of what was posted, used for deduplication.

JSON file works fine at this scale (<10k offers). Move to SQLite or
Postgres when you outgrow it. In GitHub Actions, commit this file
back to the repo after each run (or use a Gist) for persistence.
"""

import json
from datetime import datetime
from pathlib import Path

from ..models import Offer, PublishResult


class History:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"posted": {}, "results": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    def already_posted(self, offer: Offer) -> bool:
        return offer.id in self._data["posted"]

    def record(self, offer: Offer, results: list[PublishResult]) -> None:
        # Só marca como "postado" (e portanto deduplicado em runs futuros)
        # se pelo menos um canal publicou com sucesso — senão uma falha
        # transitória (rede, rate limit) descarta a oferta pra sempre.
        if any(r.success for r in results):
            self._data["posted"][offer.id] = {
                "title": offer.title,
                "posted_at": datetime.utcnow().isoformat(),
            }
        for r in results:
            self._data["results"].append(
                {
                    "offer_id": offer.id,
                    "platform": r.platform,
                    "success": r.success,
                    "post_id": r.post_id,
                    "error": r.error,
                    "at": r.published_at.isoformat(),
                }
            )

    def filter_new(self, offers: list[Offer]) -> list[Offer]:
        return [o for o in offers if not self.already_posted(o)]

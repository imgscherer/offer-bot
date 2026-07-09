"""Rule-based reviewer. Fast, deterministic, free.

Decides if a piece should be published. Returns reason on rejection so
you can debug the pipeline from logs.
"""

import re

from ..models import ContentPiece

# Words/claims that get auto-rejected (LGPD/CDC-friendly)
FORBIDDEN_CLAIMS = [
    r"\bcura\b",
    r"\bmilagre\b",
    r"\b100%\s+garantido\b",
    r"\bemagrece\s+sem\b",
]

MIN_CAPTION_LEN = 30
MAX_CAPTION_LEN = 2000


def review(piece: ContentPiece) -> tuple[bool, str]:
    """Returns (approved, reason)."""
    if len(piece.caption) < MIN_CAPTION_LEN:
        return False, "caption too short"

    if len(piece.caption) > MAX_CAPTION_LEN:
        return False, "caption too long"

    lower = piece.caption.lower()
    for pat in FORBIDDEN_CLAIMS:
        if re.search(pat, lower):
            return False, f"forbidden claim: {pat}"

    if piece.offer.discount_pct < 1:
        return False, "no real discount"

    if piece.format in {"story", "feed"} and not piece.image_path:
        return False, "missing image for visual format"

    return True, "ok"

"""Shared display formatting helpers."""

import re
from typing import Optional

# Ordered by specificity: quantity words (unidades/un/kit/pacote/c-com) beat a
# bare "NNx" since the latter also matches unrelated numbers in titles (sizes,
# model numbers, etc).
_QUANTITY_PATTERNS = [
    re.compile(r"(?:com|c/|c\.)\s*(\d+)\s*(?:unidades|unid\.?|uni\.?|und\.?|un\.?)\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:unidades|unid\.?|uni\.?|und\.?|un\.?)\b", re.IGNORECASE),
    re.compile(r"kit\s*(?:com\s*)?(\d+)\b", re.IGNORECASE),
    re.compile(r"pacote\s*(?:com\s*)?(\d+)\b", re.IGNORECASE),
    re.compile(r"leve\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*x\b", re.IGNORECASE),
]


def format_price(value: float) -> str:
    """Format a number as Brazilian currency digits: 1234.5 -> "1.234,50"."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extract_unit_count(title: str) -> Optional[int]:
    """Best-effort extraction of pack/unit quantity from an offer title.

    Returns None when no quantity is found or when it's 1 (nothing to show).
    Matches things like "60 unidades", "kit com 3", "c/ 40 un", "leve 2".
    """
    for pattern in _QUANTITY_PATTERNS:
        match = pattern.search(title)
        if match:
            qty = int(match.group(1))
            if qty > 1:
                return qty
    return None

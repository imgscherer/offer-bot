"""Shared display formatting helpers."""


def format_price(value: float) -> str:
    """Format a number as Brazilian currency digits: 1234.5 -> "1.234,50"."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

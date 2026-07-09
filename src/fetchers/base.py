"""Fetcher = anything that returns Offers. One per source."""

from abc import ABC, abstractmethod

from ..models import Niche, Offer


class Fetcher(ABC):
    """All fetchers share this contract. Add new sources by subclassing."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def fetch(self, niche: Niche, limit: int = 50) -> list[Offer]:
        """Return offers for the given niche. Should NOT raise — log and
        return [] on failure so one broken source doesn't kill the run."""

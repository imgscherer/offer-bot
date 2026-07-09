"""Publisher = anything that takes a ContentPiece and posts it somewhere.

Each channel implements this. Adding a new channel = new file, zero
changes to orchestrator.
"""

from abc import ABC, abstractmethod

from ..models import ContentPiece, PublishResult


class Publisher(ABC):
    @property
    @abstractmethod
    def platform(self) -> str: ...

    @property
    @abstractmethod
    def supported_formats(self) -> set[str]:
        """Which ContentPiece.format values this publisher handles."""

    @abstractmethod
    async def publish(self, piece: ContentPiece) -> PublishResult: ...

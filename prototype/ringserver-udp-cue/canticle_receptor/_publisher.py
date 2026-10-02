from __future__ import annotations

from typing import Protocol

from .model import VerifiedNotice


class PublisherUnavailable(Exception):
    """The private publisher could not accept a verified notice."""


class DataLinkPublisher(Protocol):
    """Private adapter seam; implementations own the DataLink TCP details."""

    def publish(self, notice: VerifiedNotice) -> None:
        """Accept one already verified, constrained notice for publication."""

"""Abstract adapter protocol: parse, normalize, and filter source records."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Iterator


class BaseAdapter(ABC):
    source: ClassVar[str]

    @abstractmethod
    def parse(self, raw_path) -> Iterator[dict]:
        """Yield one raw dict per source record (publisher-shaped keys)."""

    def normalize(self, row: dict) -> dict:
        """Mechanical cleanup. Override in subclass."""
        return row

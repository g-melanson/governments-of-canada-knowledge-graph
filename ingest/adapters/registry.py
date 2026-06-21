"""Register and resolve source adapters by name."""

from __future__ import annotations

from typing import Type

from ingest.adapters.base import BaseAdapter
from ingest.errors import UnknownSourceError

_REGISTRY: dict[str, Type[BaseAdapter]] = {}


def register(cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
    if not cls.source:
        raise ValueError(f"{cls.__name__} missing source name")
    _REGISTRY[cls.source] = cls
    return cls


def get_adapter(source: str) -> BaseAdapter:
    cls = _REGISTRY.get(source)
    if cls is None:
        raise UnknownSourceError(f"No adapter registered for source: {source}")
    return cls()


def list_sources() -> list[str]:
    return sorted(_REGISTRY)

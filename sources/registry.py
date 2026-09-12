"""Register and resolve source adapters by name."""

from __future__ import annotations
from typing import Type
from pipeline.ingest.errors import UnknownSourceError
from sources.base import BaseAdapter

_REGISTRY: dict[str, Type[BaseAdapter]] = {}
_ADAPTER_DOMAINS = (
    "sources.commons",
)

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


def _load_adapters() -> None:
    import importlib
    for domain in _ADAPTER_DOMAINS:
        importlib.import_module(domain)

def _split(source: str) -> tuple[str, str]:
    domain, resource = source.split(".", 1)
    return domain, resource

_load_adapters()

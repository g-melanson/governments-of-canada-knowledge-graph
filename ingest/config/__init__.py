"""Load source fetch configuration from ``sources.yaml``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).with_name("sources.yaml")


@lru_cache
def load_sources() -> dict[str, dict[str, Any]]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_source_config(source: str) -> dict[str, Any]:
    cfg = load_sources().get(source)
    if cfg is None:
        raise KeyError(f"Unknown source config: {source}")
    return cfg

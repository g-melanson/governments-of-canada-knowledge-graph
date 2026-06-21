"""Load source-name → LinkML schema config."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).with_name("schemas.yaml")
REPO_ROOT = CONFIG_PATH.resolve().parents[2]


@lru_cache
def load_schemas() -> dict[str, dict[str, Any]]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_schema_config(source: str) -> dict[str, Any]:
    cfg = load_schemas().get(source)
    if cfg is None:
        raise KeyError(f"Unknown schema config: {source}")
    schema_path = REPO_ROOT / cfg["schema_path"]
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return {**cfg, "schema_path": schema_path}


def list_validatable_sources() -> list[str]:
    return sorted(load_schemas())
    
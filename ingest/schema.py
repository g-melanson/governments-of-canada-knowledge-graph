from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISHER_HEADER_TAG = "gckg:publisher_header"

@lru_cache
def load_source_schema(source: str) -> dict[str, Any]:
    path = REPO_ROOT / "source" / f"{source}.schema.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)

def publisher_field_map(
    schema: dict[str, Any],
    *,
    target_class: str,
    tag: str = PUBLISHER_HEADER_TAG,
) -> dict[str, str]:
    """publisher/xml/csv header -> normalized slot name."""
    attrs = schema["classes"][target_class]["attributes"]
    out = {
        x: slot_name
        for slot_name, slot_def in attrs.items()
        if (x := (slot_def.get("annotations") or {}).get(tag))
    }
    return out

def normalized_fields(
    schema: dict[str, Any],
    *,
    target_class: str,
) -> tuple[str, ...]:
    return tuple(schema["classes"][target_class]["attributes"].keys())







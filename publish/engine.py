from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from linkml.validator import Validator, ValidationReport

from publish.context import PublishContext

PROVENANCE_KEYS = frozenset({"bronze_references", "sources", "labels", "bronze_reference"})


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL input not found: {path}")
    with path.open(encoding="utf-8") as fin:
        for line_number, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            yield line_number, json.loads(line)


def strip_for_validation(fragment: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fragment.items() if k not in PROVENANCE_KEYS}


def target_class(fragment: dict[str, Any]) -> str:
    return fragment["@type"]


class ValidationEngine:
    def __init__(self, ctx: PublishContext):
        self.ctx = ctx
        self.validator = Validator(schema=str(ctx.domain_schema_path))

    def validate_fragment(self, fragment: dict[str, Any]) -> ValidationReport:
        processed_fragment = strip_for_validation(fragment)
        return self.validator.validate(
            instance=processed_fragment,
            target_class=target_class(processed_fragment),
        )

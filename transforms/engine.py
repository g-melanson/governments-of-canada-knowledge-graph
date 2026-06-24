from dataclasses import dataclass, field

from typing import Any, Iterator
from pathlib import Path
import json
import importlib

from transforms.errors import BronzeInputError


@dataclass
class TransformationOutcome:
    line_number: int
    record: dict[str, Any]
    fragments: list[dict[str, Any]]
    accepted: bool


@dataclass
class TransformationSummary:
    record_count: int = 0
    fragment_count: int = 0
    rejected_count: int = 0
    accepted_count: int = 0


def _load_factory(dotted_path: str):
    module_path, fn_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)

def iter_bronze_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise BronzeInputError(f"Bronze records not found: {path}")

    with path.open(encoding="utf-8") as fin:
        for line_number, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            yield line_number, json.loads(line)


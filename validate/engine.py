"""LinkML validation engine for JSONL staging records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from linkml.validator.report import Severity

from validate.errors import StagingInputError


@dataclass
class RecordOutcome:
    line_number: int
    record: dict[str, Any]
    accepted: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationSummary:
    input_record_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)


def iter_staging_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise StagingInputError(f"Staging records not found: {path}")
    with path.open(encoding="utf-8") as fin:
        for line_number, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            yield line_number, json.loads(line)


def validate_records(
    records_path: Path,
    schema_path: Path,
    target_class: str,
    *,
    fail_fast: bool = False,
) -> tuple[list[RecordOutcome], ValidationSummary]:
    validator = Validator(
        str(schema_path),
        validation_plugins=[JsonschemaValidationPlugin(closed=True)],
        strict=fail_fast,
    )
    outcomes: list[RecordOutcome] = []
    summary = ValidationSummary()

    for line_number, record in iter_staging_records(records_path):
        summary.input_record_count += 1
        report = validator.validate(record, target_class=target_class)
        errors = [
            {
                "message": r.message,
                "severity": r.severity.name if r.severity else "ERROR",
                "slot": getattr(r, "instantiates", None) or getattr(r, "source", None),
            }
            for r in report.results
            if r.severity in (Severity.ERROR, Severity.FATAL) or r.severity is None
        ]
        accepted = len(errors) == 0
        outcome = RecordOutcome(
            line_number=line_number,
            record=record,
            accepted=accepted,
            errors=errors,
        )
        outcomes.append(outcome)

        if accepted:
            summary.accepted_count += 1
        else:
            summary.rejected_count += 1
            for err in errors:
                key = str(err.get("slot") or err.get("message") or "unknown")
                summary.error_counts[key] = summary.error_counts.get(key, 0) + 1
            if fail_fast:
                break

    return outcomes, summary

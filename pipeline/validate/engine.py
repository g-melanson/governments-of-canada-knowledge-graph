"""LinkML validation engine for JSONL staging records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from linkml.validator import Validator
from linkml.validator.report import Severity

import logging

logging.getLogger("linkml").setLevel(logging.ERROR)


@dataclass
class RecordOutcome:
    record: dict[str, Any]
    accepted: bool
    errors: list[dict[str, Any]] = field(default_factory=list)


def validate_record(
    record: dict[str, Any],
    target_class: str,
    validator: Validator,
) -> RecordOutcome:

    record_class = record.get("_row_class", target_class)
    payload = {k: v for k, v in record.items() if k != "_row_class"}
    report = validator.validate(payload, target_class=record_class)
    errors = [
        {
            "message": r.message,
            "severity": r.severity.name if r.severity else "ERROR",
            "slot": getattr(r, "instantiates", None) or getattr(r, "source", None),
        }
        for r in report.results
        if r.severity in (Severity.ERROR, Severity.FATAL) or r.severity is None
    ]

    if errors:
        return RecordOutcome(
            record=record,
            accepted=False,
            errors=errors,
        )

    else:
        return RecordOutcome(
            record=record,
            accepted=True,
            errors=[],
        )

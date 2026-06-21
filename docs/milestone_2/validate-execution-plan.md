# Execution plan — Stage 2 Validate (Bronze gate)

**Stage 2** validates Stage 1 `records.jsonl` against **LinkML source schemas** (`source/*.schema.yaml`), writes **Bronze** (source-validated records), and routes failures to **quarantine** with a drift report.

Pilot source: **`commons_members`** (small, HTTP-friendly, tests already exist).  
Second source: **`open_canada_federal_election_contribution`** (proves large-file streaming validation).

Implement files **top to bottom**. Each section: **what it does** → **exact code or schema**.

---

## Prerequisites

| Requirement | Status |
|-------------|--------|
| Stage 1 staging layout | `staging/{source}/{run_id}/records.jsonl` + `manifest.json` |
| `commons_members` adapter | Implemented |
| `source/` LinkML schemas | **Create in this milestone** |
| `linkml` + validator in venv | `pip install linkml` (includes `linkml-validate` CLI) |

**Handoff contract:** Validate reads **staging**, never re-fetches publishers. Provenance chains through manifests.

```text
staging/{source}/{run_id}/records.jsonl  ──►  Validate  ──►  bronze/{source}/{run_id}/records.jsonl
                                              │
                                              └──►  quarantine/{source}/{run_id}/rejects.jsonl
                                                    quarantine/{source}/{run_id}/drift_report.json
```

---

## Design decisions (locked for M2)

1. **Source schemas live in `source/`** — separate from `domain_model/` (domain = Stage 5 gate).
2. **Slot names match Stage 1 JSONL keys** — snake_case as emitted by adapters (`person_id`, not `PersonId`).
3. **One LinkML class per source row** — e.g. `MemberOfParliamentRow`, not domain entities.
4. **Validation is config-driven** — no per-source Python validator classes unless a source needs custom pre-checks later.
5. **Stream JSONL line-by-line** — do not load 6M-row files into memory.
6. **Default: collect all rejects** — `--fail-fast` optional for CI schema-drift checks.
7. **Bronze records are identical to accepted staging rows** — no transform, no GCKG IDs (Stage 3 job).

---

## Source specification — `commons_members`

Stage 1 output shape (from `ingest/adapters/commons/members.py`):

| JSONL field | LinkML slot | Required | Notes |
|-------------|-------------|----------|-------|
| `person_id` | `person_id` | yes | string |
| `person_short_honorific` | `person_short_honorific` | no | |
| `person_official_first_name` | `person_official_first_name` | no | |
| `person_official_last_name` | `person_official_last_name` | no | |
| `constituency_name` | `constituency_name` | no | |
| `constituency_province_territory_name` | `constituency_province_territory_name` | no | |
| `caucus_short_name` | `caucus_short_name` | no | |
| `from_date_time` | `from_date_time` | no | ISO 8601 string |
| `to_date_time` | `to_date_time` | no | null = current member |

---

## 0. Package manifest

**What:** Add `validate` package and LinkML deps to the existing project.

**File:** `pyproject.toml` (append / merge)

```toml
[project]
name = "gckg"
version = "0.2.0"
description = "GCKG pipeline — ingest (Stage 1) and validate (Stage 2)"
requires-python = ">=3.9"
dependencies = [
  "pyyaml>=6.0",
  "requests>=2.31",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]
validate = ["linkml>=1.9.0"]

[project.scripts]
ingest = "ingest.cli:main"
validate = "validate.cli:main"

[tool.setuptools.packages.find]
include = ["ingest*", "validate*"]

[tool.pytest.ini_options]
testpaths = ["ingest/tests", "validate/tests"]
```

```bash
pip install -e ".[dev,validate]"
```

---

## 1. Source schema — `commons_members`

**What:** LinkML contract for one staged MP row. Build-time lint: `gen-yaml source/commons_members.schema.yaml`.

**File:** `source/commons_members.schema.yaml`

```yaml
id: https://w3id.org/gckg/source/commons_members
name: commons_members_source
title: Commons members — staged row shape
description: Source schema for Stage 1 JSONL from ourcommons.ca MemberOfParliament XML.
version: 0.1.0

prefixes:
  linkml: https://w3id.org/linkml/
  gckg_src: https://w3id.org/gckg/source/commons_members/

default_prefix: gckg_src

imports:
  - linkml:types

classes:
  MemberOfParliamentRow:
    tree_root: true
    description: One tenure row per MemberOfParliament element.
    attributes:
      person_id:
        range: string
        required: true
      person_short_honorific:
        range: string
      person_official_first_name:
        range: string
      person_official_last_name:
        range: string
      constituency_name:
        range: string
      constituency_province_territory_name:
        range: string
      caucus_short_name:
        range: string
      from_date_time:
        range: string
      to_date_time:
        range: string
```

**Build check:**

```bash
cd source && gen-yaml commons_members.schema.yaml
```

---

## 2. Schema registry config

**What:** Maps ingest source name → LinkML schema file + target class.

**File:** `validate/config/schemas.yaml`

```yaml
commons_members:
  schema_path: source/commons_members.schema.yaml
  target_class: MemberOfParliamentRow

open_canada_federal_election_contribution:
  schema_path: source/open_canada_federal_election_contribution.schema.yaml
  target_class: FederalElectionContributionRow
```

**File:** `validate/config/__init__.py`

```python
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
```

---

## 3. Errors

**File:** `validate/errors.py`

```python
"""Typed exceptions for Stage 2 validation."""


class ValidateError(Exception):
    """Base class for validation-stage failures."""


class StagingInputError(ValidateError):
    """Staging records.jsonl or manifest missing or unreadable."""


class SchemaConfigError(ValidateError):
    """Schema registry misconfigured or schema file missing."""


class ValidationFailedError(ValidateError):
    """One or more records failed validation (--fail-fast mode)."""


class EmptyBronzeError(ValidateError):
    """All records rejected; Bronze would be empty."""
```

---

## 4. Validate context

**What:** Immutable per-run paths and policy. Mirrors `ingest.context.RunContext`.

**File:** `validate/context.py`

```python
"""Immutable per-run settings for Stage 2 validate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidateContext:
    source: str
    run_id: str
    staging_run_id: str
    staging_root: Path = Path("staging")
    bronze_root: Path = Path("bronze")
    quarantine_root: Path = Path("quarantine")
    fail_fast: bool = False

    @property
    def staging_run_dir(self) -> Path:
        return self.staging_root / self.source / self.staging_run_id

    @property
    def staging_records_path(self) -> Path:
        return self.staging_run_dir / "records.jsonl"

    @property
    def staging_manifest_path(self) -> Path:
        return self.staging_run_dir / "manifest.json"

    @property
    def bronze_run_dir(self) -> Path:
        return self.bronze_root / self.source / self.run_id

    @property
    def bronze_records_path(self) -> Path:
        return self.bronze_run_dir / "records.jsonl"

    @property
    def bronze_manifest_path(self) -> Path:
        return self.bronze_run_dir / "manifest.json"

    @property
    def quarantine_run_dir(self) -> Path:
        return self.quarantine_root / self.source / self.run_id

    @property
    def rejects_path(self) -> Path:
        return self.quarantine_run_dir / "rejects.jsonl"

    @property
    def drift_report_path(self) -> Path:
        return self.quarantine_run_dir / "drift_report.json"
```

---

## 5. Validator core

**What:** Stream JSONL, validate each dict against LinkML, partition into accepted / rejected.

**File:** `validate/engine.py`

```python
"""LinkML validation engine for JSONL staging records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from linkml.validator import Validator
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
    validator = Validator(str(schema_path))
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
```

---

## 6. Runner

**What:** Orchestrate validate → write Bronze + quarantine + manifests.

**File:** `validate/runner.py`

```python
"""Orchestrate LinkML validation and Bronze/quarantine output."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from validate.config import get_schema_config
from validate.context import ValidateContext
from validate.engine import validate_records
from validate.errors import EmptyBronzeError, StagingInputError, ValidationFailedError

log = logging.getLogger(__name__)


def run_validate(ctx: ValidateContext) -> dict:
    schema_cfg = get_schema_config(ctx.source)
    if not ctx.staging_manifest_path.exists():
        raise StagingInputError(f"Staging manifest not found: {ctx.staging_manifest_path}")

    staging_manifest = json.loads(ctx.staging_manifest_path.read_text(encoding="utf-8"))
    ctx.bronze_run_dir.mkdir(parents=True, exist_ok=True)
    ctx.quarantine_run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    outcomes, summary = validate_records(
        ctx.staging_records_path,
        schema_cfg["schema_path"],
        schema_cfg["target_class"],
        fail_fast=ctx.fail_fast,
    )

    if summary.accepted_count == 0:
        raise EmptyBronzeError(f"{ctx.source}: all records rejected")

    with ctx.bronze_records_path.open("w", encoding="utf-8") as bout:
        with ctx.rejects_path.open("w", encoding="utf-8") as qout:
            for outcome in outcomes:
                if outcome.accepted:
                    bout.write(json.dumps(outcome.record, ensure_ascii=False) + "\n")
                else:
                    qout.write(
                        json.dumps(
                            {
                                "line": outcome.line_number,
                                "record": outcome.record,
                                "errors": outcome.errors,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

    finished_at = datetime.now(timezone.utc)
    drift_report = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "staging_run_id": ctx.staging_run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "schema_path": str(schema_cfg["schema_path"].relative_to(schema_cfg["schema_path"].parents[2])
                         if schema_cfg["schema_path"].is_absolute() else schema_cfg["schema_path"]),
        "target_class": schema_cfg["target_class"],
        "input_record_count": summary.input_record_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "error_counts": summary.error_counts,
        "fail_fast": ctx.fail_fast,
    }
    ctx.drift_report_path.write_text(json.dumps(drift_report, indent=2), encoding="utf-8")

    bronze_manifest = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "stage": "validate",
        "tier": "bronze",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [
            {
                "staging_run_id": ctx.staging_run_id,
                "staging_manifest": json.loads(ctx.staging_manifest_path.read_text(encoding="utf-8")),
            }
        ],
        "output": {
            "records_path": "records.jsonl",
            "record_count": summary.accepted_count,
            "rejected_count": summary.rejected_count,
            "drift_report_path": str(ctx.drift_report_path),
        },
    }
    ctx.bronze_manifest_path.write_text(json.dumps(bronze_manifest, indent=2), encoding="utf-8")

    if ctx.fail_fast and summary.rejected_count > 0:
        raise ValidationFailedError(f"{ctx.source}: validation failed under --fail-fast")

    log.info(
        "validate_complete",
        extra={
            "source": ctx.source,
            "run_id": ctx.run_id,
            "accepted": summary.accepted_count,
            "rejected": summary.rejected_count,
        },
    )
    return bronze_manifest
```

---

## 7. CLI

**File:** `validate/cli.py`

```python
"""CLI for Stage 2 validate."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from validate.config import list_validatable_sources
from validate.context import ValidateContext
from validate.runner import run_validate


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="validate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Validate staging records → Bronze")
    run_p.add_argument("--source", required=True)
    run_p.add_argument("--staging-run-id", required=True, help="Stage 1 run_id under staging/")
    run_p.add_argument("--run-id", default=_default_run_id())
    run_p.add_argument("--staging-root", type=Path, default=Path("staging"))
    run_p.add_argument("--bronze-root", type=Path, default=Path("bronze"))
    run_p.add_argument("--quarantine-root", type=Path, default=Path("quarantine"))
    run_p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first invalid record (CI schema drift)",
    )

    sub.add_parser("list-sources", help="List sources with source schemas")

    args = parser.parse_args()
    if args.command == "list-sources":
        for name in list_validatable_sources():
            print(name)
        return

    ctx = ValidateContext(
        source=args.source,
        run_id=args.run_id,
        staging_run_id=args.staging_run_id,
        staging_root=args.staging_root,
        bronze_root=args.bronze_root,
        quarantine_root=args.quarantine_root,
        fail_fast=args.fail_fast,
    )
    manifest = run_validate(ctx)
    print(json.dumps(manifest["output"], indent=2))
```

**File:** `validate/__main__.py`

```python
from validate.cli import main

if __name__ == "__main__":
    main()
```

---

## 8. Tests

**What:** Offline tests — no network. Use existing ingest fixtures.

**Layout:**

```text
validate/tests/
├── conftest.py
├── test_engine_commons_members.py
└── fixtures/
    ├── valid_row.json
    └── invalid_row_missing_person_id.json
```

**File:** `validate/tests/test_engine_commons_members.py` (sketch)

```python
from pathlib import Path
import json
import pytest
from validate.engine import validate_records

SCHEMA = Path("source/commons_members.schema.yaml")
FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_row_passes(tmp_path: Path) -> None:
    row = json.loads((FIXTURES / "valid_row.json").read_text())
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps(row) + "\n")
    outcomes, summary = validate_records(records, SCHEMA, "MemberOfParliamentRow")
    assert summary.accepted_count == 1
    assert summary.rejected_count == 0


def test_missing_person_id_rejected(tmp_path: Path) -> None:
    row = json.loads((FIXTURES / "invalid_row_missing_person_id.json").read_text())
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps(row) + "\n")
    outcomes, summary = validate_records(records, SCHEMA, "MemberOfParliamentRow")
    assert summary.rejected_count == 1
    assert not outcomes[0].accepted
```

**Integration test:** Run ingest on `commons_members_sample.xml`, then validate that staging run.

---

## 9. Manual run (end-to-end)

```bash
pip install -e ".[dev,validate]"

# Stage 1 (if needed)
python -m ingest run --source commons_members \
  --fetch-policy local-file \
  --input ingest/tests/fixtures/raw/commons_members_sample.xml \
  --run-id m2-staging-test

# Stage 2
python -m validate run \
  --source commons_members \
  --staging-run-id m2-staging-test

# Inspect
ls bronze/commons_members/m2-staging-test/
ls quarantine/commons_members/*/   # only if rejects exist
cat bronze/commons_members/*/manifest.json
```

**Contributions (large file):**

```bash
python -m validate run \
  --source open_canada_federal_election_contribution \
  --staging-run-id 2026-06-14T233158Z
```

Validation streams line-by-line; memory stays bounded.

---

## 10. Adapter rollout order

| Order | Source | Schema file | Notes |
|-------|--------|-------------|-------|
| 1 | `commons_members` | `source/commons_members.schema.yaml` | Pilot; small; tests |
| 2 | `open_canada_federal_election_contribution` | `source/open_canada_federal_election_contribution.schema.yaml` | 27 slots; BOM rule optional |
| 3 | `open_canada_expenditure` | TBD | After expenditure adapter lands |
| 4 | `commons_votes` | TBD | Reuse XML patterns |
| 5 | `commons_petitions` | TBD | |
| 6 | `udc_districts` | TBD | |

**Catalog validation (recommended):** At startup, assert `validate/config/schemas.yaml` keys match registered ingest sources you intend to validate.

---

## 11. Done criteria

- [ ] `source/commons_members.schema.yaml` passes `gen-yaml`
- [ ] `validate/` package installable; `python -m validate list-sources` works
- [ ] `python -m validate run --source commons_members --staging-run-id …` writes:
  - `bronze/{source}/{run_id}/records.jsonl`
  - `bronze/{source}/{run_id}/manifest.json`
  - `quarantine/…/drift_report.json` (and `rejects.jsonl` if any rejects)
- [ ] Valid staging rows → Bronze unchanged (byte-level JSON equality per record)
- [ ] Invalid row (missing `person_id`) → quarantine with error detail
- [ ] `pytest validate/tests` passes offline
- [ ] Contributions validation completes on full staging run without OOM
- [ ] README updated: Stage 2 section links to this plan

---

## 12. Follow-on (Stage 3 — Transform / Silver)

Not this milestone:

- `transforms/commons_members_to_gckg.yaml` (LinkML-Map)
- Silver graph fragments under `silver/{source}/{run_id}/`
- Domain IDs introduced at transform, not validate

---

## 13. File layout (after M2)

```text
gckg/
├── source/                              # LinkML source schemas · Validate gate
│   ├── commons_members.schema.yaml
│   └── open_canada_federal_election_contribution.schema.yaml
│
├── validate/                              # Python package · Stage 2 Validate
│   ├── __main__.py
│   ├── cli.py
│   ├── runner.py
│   ├── context.py
│   ├── engine.py
│   ├── errors.py
│   ├── config/
│   │   └── schemas.yaml
│   └── tests/
│
├── staging/                               # Stage 1 output (input to Validate)
├── bronze/                                # Stage 2 output
└── quarantine/                            # rejects + drift_report.json
```

---

## 14. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Stage 1 / schema slot drift | CI test: ingest fixture → validate must pass |
| 6M-row contributions slow | Stream JSONL; optional chunked progress logging |
| LinkML required vs optional mismatch | Schema `required: true` only for adapter-required fields |
| UTF-8 BOM in CSV fields | Optional `pattern` or pre-normalize rule in schema later |
| Empty Bronze after bad run | `EmptyBronzeError`; drift report still written |

---

## 15. Relationship to domain model

| Layer | Path | When |
|-------|------|------|
| Source schema | `source/*.schema.yaml` | **Stage 2** — publisher-shaped rows |
| Domain model | `domain_model/` | **Stage 5** — graph-native entities |
| Transform map | `transforms/*.yaml` | **Stage 3** — source → domain |

Do **not** validate staging JSONL against `domain_model/schema.yaml` in Stage 2. That gate is Publish (Stage 5).

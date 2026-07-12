"""Orchestrate Bronze → Silver transformation.

Two execution paths depending on the source's maps.yaml entry:

- ``map_mode: yaml``  — YAML-driven path via ``YamlMapEngine``. The
  ``class_derivations`` in the transform spec are compiled into a dispatch
  table; ``expr`` strings are evaluated per row.  No Python materializer
  needed.
- *(default)*         — Python materializer path (legacy). ``materializer``
  key must point to a ``get_materializer`` factory function.

Both paths produce the same Silver JSONL output so the rest of the pipeline
is unaffected.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.transforms.context import TransformContext
from pipeline.transforms.errors import RowMaterializationError
from pipeline.transforms.config import load_maps
from pipeline.transforms.engine import (
    _load_factory,
    iter_bronze_records,
    TransformationSummary,
    TransformationOutcome,
)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_engine(map_cfg: dict, ctx: TransformContext):
    """Return a materializer-compatible object for the given map config."""
    if map_cfg.get("map_mode") == "yaml":
        from pipeline.transforms.map_engine import YamlMapEngine

        map_path = REPO_ROOT / map_cfg["map_path"]

        def bronze_reference_factory(line_number: int) -> dict:
            return {
                "source": ctx.source,
                "bronze_run_id": ctx.bronze_run_id,
                "line_number": line_number,
            }

        return YamlMapEngine(
            map_path,
            bronze_reference_factory,
            default_row_class=map_cfg.get("source_class"),
        )

    factory = _load_factory(map_cfg["materializer"])
    return factory(ctx)


def run_transform(ctx: TransformContext) -> dict:
    ctx.silver_dir.mkdir(parents=True, exist_ok=True)

    map_cfg = load_maps()[ctx.source]
    engine = _build_engine(map_cfg, ctx)

    outcomes: list[TransformationOutcome] = []
    summary = TransformationSummary()
    started_at = datetime.now(timezone.utc)

    for line_number, record in iter_bronze_records(ctx.bronze_records_path):
        summary.record_count += 1
        try:
            fragments = list(engine.materialize(record, line_number))
        except RowMaterializationError as e:
            log.error(f"Error materializing row {line_number}: {e}")
            summary.rejected_count += 1
            outcomes.append(
                TransformationOutcome(
                    line_number=line_number,
                    record=record,
                    fragments=[],
                    accepted=False,
                )
            )
            continue

        summary.accepted_count += 1
        outcomes.append(
            TransformationOutcome(
                line_number=line_number,
                record=record,
                fragments=fragments,
                accepted=True,
            )
        )

    with ctx.silver_fragments_path.open("w", encoding="utf-8") as fout:
        with ctx.quarantine_path.open("w", encoding="utf-8") as qout:
            for outcome in outcomes:
                if not outcome.accepted:
                    qout.write(json.dumps(outcome.record, ensure_ascii=False) + "\n")
                else:
                    for fragment in outcome.fragments:
                        fout.write(
                            json.dumps(fragment, ensure_ascii=False) + "\n"
                        )
                        summary.fragment_count += 1

    finished_at = datetime.now(timezone.utc)

    map_mode = map_cfg.get("map_mode", "materializer")
    silver_manifest = {
        "run_id": ctx.run_id,
        "bronze_run_id": ctx.bronze_run_id,
        "source": ctx.source,
        "stage": "transform",
        "tier": "silver",
        "map_mode": map_mode,
        "transform_map": str(map_cfg["map_path"]),
        "materializer": map_cfg.get("materializer"),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [
            {
                "bronze_run_id": ctx.bronze_run_id,
                "bronze_manifest_path": str(ctx.bronze_manifest_path),
            }
        ],
        "output": {
            "fragments_path": str(ctx.silver_fragments_path),
            "quarantine_path": str(ctx.quarantine_path),
            "fragment_count": summary.fragment_count,
            "record_count": summary.record_count,
            "accepted_count": summary.accepted_count,
            "rejected_count": summary.rejected_count,
        },
    }

    ctx.silver_manifest_path.write_text(
        json.dumps(silver_manifest, indent=2), encoding="utf-8"
    )
    log.info(
        "transform_complete",
        extra={
            "source": ctx.source,
            "run_id": ctx.run_id,
            "map_mode": map_mode,
            "accepted": summary.accepted_count,
            "rejected": summary.rejected_count,
        },
    )
    return silver_manifest

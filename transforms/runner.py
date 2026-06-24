
#silver manifest
#main run function
#write silver jsonl
#write quarantine jsonl
#add progress tracker

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from transforms.context import TransformContext
from transforms.errors import RowMaterializationError
from transforms.config import load_maps
from transforms.engine import (
    _load_factory,
    iter_bronze_records,
    TransformationSummary,
    TransformationOutcome,
)


log = logging.getLogger(__name__)


def run_transform(ctx: TransformContext) -> dict:

    if not ctx.silver_dir.exists():
        ctx.silver_dir.mkdir(parents=True, exist_ok=True)

    map_cfg = load_maps()[ctx.source]
    factory = _load_factory(map_cfg["materializer"])
    materializer = factory(ctx)

    outcomes: list[TransformationOutcome] = []
    summary = TransformationSummary()

    started_at = datetime.now(timezone.utc)

    for line_number, record in iter_bronze_records(ctx.bronze_records_path):
        summary.record_count += 1

        try:
            fragments = list(materializer.materialize(record, line_number))

        except RowMaterializationError as e:
            log.error(f"Error materializing row {line_number}: {e}")
            summary.rejected_count += 1
            outcomes.append(TransformationOutcome(
                line_number=line_number,
                record=record,
                fragments=[],
                accepted=False))
            continue

        summary.accepted_count += 1
        outcomes.append(TransformationOutcome(
            line_number=line_number,
            record=record,
            fragments=fragments,
            accepted=True))

    with ctx.silver_fragments_path.open("w", encoding="utf-8") as fout:
        with ctx.quarantine_path.open("w", encoding="utf-8") as qout:
            for outcome in outcomes:
                if not outcome.accepted:
                    qout.write(json.dumps(outcome.record, ensure_ascii=False) + "\n")
                else:
                    for fragment in outcome.fragments:
                        fout.write(json.dumps(fragment, ensure_ascii=False) + "\n")
                        summary.fragment_count += 1

    finished_at = datetime.now(timezone.utc)

    silver_manifest = {
        "run_id": ctx.run_id,
        "bronze_run_id": ctx.bronze_run_id,
        "source": ctx.source,
        "stage": "transform",
        "tier": "silver",
        "transform_map": str(map_cfg["map_path"]),
        "source_class": map_cfg["source_class"],
        "materializer": map_cfg["materializer"],
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
        }
    }

    ctx.silver_manifest_path.write_text(json.dumps(silver_manifest, indent=2), encoding="utf-8")

    log.info(
        "transform_complete",
        extra={
            "source": ctx.source,
            "run_id": ctx.run_id,
            "accepted": summary.accepted_count,
            "rejected": summary.rejected_count,
        },
    )
    return silver_manifest

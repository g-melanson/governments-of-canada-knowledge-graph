"""Orchestrate fetch, parse, normalize, filter, and write staging outputs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sources.registry import get_adapter, _load_adapters
from pipeline.ingest.config import get_source_config
from pipeline.ingest.context import RunContext
from pipeline.ingest.errors import EmptySourceError
from pipeline.ingest.fetch.client import fetch_raw
from pipeline.ingest.normalize import SchemaNormalizer
from pipeline.ingest.utils import staging_json_default

log = logging.getLogger(__name__)


def build_adapter(source: str):
    _load_adapters()
    return get_adapter(source)


def run_ingest(ctx: RunContext) -> dict:
    adapter = build_adapter(ctx.source)
    source_cfg = get_source_config(ctx.source)
    normalizer = SchemaNormalizer(ctx.schema_path)

    ctx.run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    raw_path, input_meta = fetch_raw(ctx, source_cfg)

    record_count = 0
    rejected_count = 0
    with ctx.records_path.open("w", encoding="utf-8") as fout:
        for raw_row in adapter.parse(raw_path):
            row = normalizer.normalize(raw_row["_row_class"], raw_row)
            fout.write(json.dumps(row, ensure_ascii=False, default=staging_json_default) + "\n")
            record_count += 1

    if record_count == 0:
        raise EmptySourceError(f"{ctx.source} produced zero records")

    finished_at = datetime.now(timezone.utc)
    manifest = {
        "run_id": ctx.run_id,
        "source": ctx.source,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [input_meta],
        "output": {
            "records_path": "records.jsonl",
            "record_count": record_count,
            "rejected_count": rejected_count,
        },
    }
    ctx.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info(
        "ingest_complete",
        extra={
            "source": ctx.source,
            "run_id": ctx.run_id,
            "record_count": record_count,
            "rejected_count": rejected_count,
        },
    )
    return manifest

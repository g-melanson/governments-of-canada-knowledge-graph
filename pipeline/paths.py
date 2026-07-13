"""Canonical runtime output paths under universe/.

Layout: universe/{run_id}/{tier}/{source}/…
Contract: pipeline/README.md (Universe output layout section)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

STAGING = "1-staging"
BRONZE = "2-bronze"
SILVER = "3-silver"
MERGED = "4-merged"
GOLD = "5-gold"
CACHE = "cache"
QUARANTINE = "quarantine"

RECORDS_JSONL = "records.jsonl"
FRAGMENTS_JSONL = "fragments.jsonl"
NODES_JSONL = "nodes.jsonl"
EDGES_JSONL = "edges.jsonl"
MANIFEST_JSON = "manifest.json"
REJECTS_JSONL = "rejects.jsonl"
DRIFT_REPORT_JSON = "drift_report.json"
RESOLUTION_REPORT_JSON = "resolution_report.json"
QUARANTINE_JSONL = "quarantine.jsonl"
RAW_DIR = "raw"
MAP_JSON = "map.json"
GOLD_QUARANTINE_DIR = "quarantine"


@dataclass(frozen=True)
class UniversePaths:
    """All runtime pipeline output paths.

    Paths are grouped by pipeline ``run_id`` so one E2E run lives under
    ``universe/{run_id}/`` (staging, bronze, silver, merged, gold, quarantine).

    HTTP fetch cache stays shared at ``universe/cache/{source}/``.
    """

    root: Path = Path("universe")

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "root",
            self.root if self.root.is_absolute() else REPO_ROOT / self.root,
        )

    def run_root(self, run_id: str) -> Path:
        return self.root / run_id

    def source_cache_dir(self, source: str) -> Path:
        return self.root / CACHE / source

    # ── per-source tiers (under universe/{run_id}/) ──

    def staging_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / STAGING / source

    def bronze_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / BRONZE / source

    def silver_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / SILVER / source

    def validate_quarantine_run_dir(self, source: str, run_id: str) -> Path:
        return self.run_root(run_id) / QUARANTINE / source

    def merged_run_dir(self, run_id: str) -> Path:
        return self.run_root(run_id) / MERGED

    def gold_run_dir(self, run_id: str) -> Path:
        return self.run_root(run_id) / GOLD

    # ── file paths ──

    def staging_records(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / RECORDS_JSONL

    def staging_raw_dir(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / RAW_DIR

    def staging_manifest(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / MANIFEST_JSON

    def bronze_records(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / RECORDS_JSONL

    def bronze_manifest(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / MANIFEST_JSON

    def silver_fragments(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / FRAGMENTS_JSONL

    def silver_quarantine(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / QUARANTINE_JSONL

    def silver_manifest(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / MANIFEST_JSON

    def silver_map(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / MAP_JSON

    def validate_quarantine_rejects(self, source: str, run_id: str) -> Path:
        return self.validate_quarantine_run_dir(source, run_id) / REJECTS_JSONL

    def validate_quarantine_drift_report(self, source: str, run_id: str) -> Path:
        return self.validate_quarantine_run_dir(source, run_id) / DRIFT_REPORT_JSON

    def merged_nodes(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / NODES_JSONL

    def merged_edges(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / EDGES_JSONL

    def merged_quarantine(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / QUARANTINE_JSONL

    def merged_resolution_report(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / RESOLUTION_REPORT_JSON

    def merged_manifest(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / MANIFEST_JSON

    def gold_nodes(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / NODES_JSONL

    def gold_edges(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / EDGES_JSONL

    def gold_manifest(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / MANIFEST_JSON

    def gold_quarantine_dir(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / GOLD_QUARANTINE_DIR

    def gold_quarantine_nodes(self, run_id: str) -> Path:
        return self.gold_quarantine_dir(run_id) / NODES_JSONL

    def gold_quarantine_edges(self, run_id: str) -> Path:
        return self.gold_quarantine_dir(run_id) / EDGES_JSONL


DEFAULT_PATHS = UniversePaths()

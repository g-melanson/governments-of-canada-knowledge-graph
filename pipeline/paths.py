"""Canonical runtime output paths under universe/.

Contract: universe/README.md
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ── Layer A: repo anchor + tier segment names ──────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]

STAGING = "1-staging"
BRONZE = "2-bronze"
SILVER = "3-silver"
MERGED = "4-merged"      # fix README typo: not 4-silver
GOLD = "5-gold"
CACHE = "cache"
QUARANTINE = "quarantine"  # validate-tier rejects (global under universe)

# Layer A: filenames (avoid typos across stages)
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


# ── Layer B + C: UniversePaths ─────────────────────────────────────────────

@dataclass(frozen=True)
class UniversePaths:
    """All runtime pipeline output paths.

    Args:
        root: Absolute or relative path to the universe root directory.
              Relative paths are resolved against REPO_ROOT.
    """

    root: Path = Path("universe")

    def __post_init__(self) -> None:
        # dataclass frozen trick: normalize to absolute path once
        object.__setattr__(
            self,
            "root",
            self.root if self.root.is_absolute() else REPO_ROOT / self.root,
        )

    # ── tier roots (Layer B) ──

    @property
    def staging(self) -> Path:
        return self.root / STAGING

    @property
    def bronze(self) -> Path:
        return self.root / BRONZE

    @property
    def silver(self) -> Path:
        return self.root / SILVER

    @property
    def merged(self) -> Path:
        return self.root / MERGED

    @property
    def gold(self) -> Path:
        return self.root / GOLD

    @property
    def cache(self) -> Path:
        return self.root / CACHE

    @property
    def quarantine(self) -> Path:
        return self.root / QUARANTINE

    # ── per-source run dirs (Layer C) ──

    def staging_run_dir(self, source: str, run_id: str) -> Path:
        return self.staging / source / run_id

    def bronze_run_dir(self, source: str, run_id: str) -> Path:
        return self.bronze / source / run_id

    def silver_run_dir(self, source: str, run_id: str) -> Path:
        return self.silver / source / run_id

    def validate_quarantine_run_dir(self, source: str, run_id: str) -> Path:
        """Stage 2 rejects — universe/quarantine/{source}/{run_id}/"""
        return self.quarantine / source / run_id

    def merged_run_dir(self, run_id: str) -> Path:
        return self.merged / run_id

    def gold_run_dir(self, run_id: str) -> Path:
        return self.gold / run_id

    def source_cache_dir(self, source: str) -> Path:
        return self.cache / source

    # ── common file paths (Layer C, file granularity) ──

    def staging_records(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / RECORDS_JSONL

    def staging_raw_dir(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / RAW_DIR

    def bronze_records(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / RECORDS_JSONL

    def silver_fragments(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / FRAGMENTS_JSONL

    def silver_quarantine(self, source: str, run_id: str) -> Path:
        """Transform-stage quarantine — lives INSIDE the silver run dir."""
        return self.silver_run_dir(source, run_id) / QUARANTINE_JSONL

    def merged_nodes(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / NODES_JSONL

    def validate_quarantine_rejects(self, source: str, run_id: str) -> Path:
        return self.validate_quarantine_run_dir(source, run_id) / REJECTS_JSONL

    def validate_quarantine_drift_report(self, source: str, run_id: str) -> Path:
        return self.validate_quarantine_run_dir(source, run_id) / DRIFT_REPORT_JSON

    def silver_map(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / MAP_JSON

    def merged_edges(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / EDGES_JSONL

    def merged_quarantine(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / QUARANTINE_JSONL

    def merged_resolution_report(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / RESOLUTION_REPORT_JSON

    def gold_nodes(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / NODES_JSONL

    def gold_edges(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / EDGES_JSONL

    def gold_quarantine_dir(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / GOLD_QUARANTINE_DIR

    def gold_quarantine_nodes(self, run_id: str) -> Path:
        return self.gold_quarantine_dir(run_id) / NODES_JSONL

    def gold_quarantine_edges(self, run_id: str) -> Path:
        return self.gold_quarantine_dir(run_id) / EDGES_JSONL

    # ── manifests ─────────────────────────────────────────────────────────── #
    def staging_manifest(self, source: str, run_id: str) -> Path:
        return self.staging_run_dir(source, run_id) / MANIFEST_JSON

    def bronze_manifest(self, source: str, run_id: str) -> Path:
        return self.bronze_run_dir(source, run_id) / MANIFEST_JSON

    def silver_manifest(self, source: str, run_id: str) -> Path:
        return self.silver_run_dir(source, run_id) / MANIFEST_JSON

    def merged_manifest(self, run_id: str) -> Path:
        return self.merged_run_dir(run_id) / MANIFEST_JSON

    def gold_manifest(self, run_id: str) -> Path:
        return self.gold_run_dir(run_id) / MANIFEST_JSON

# Default instance — import this when you don't need overrides
DEFAULT_PATHS = UniversePaths()
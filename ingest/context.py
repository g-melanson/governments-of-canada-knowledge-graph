"""Immutable per-run settings: staging paths, fetch policy, and adapter flags."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FetchPolicy = Literal["default", "refresh", "cache-only", "local-file"]


@dataclass(frozen=True)
class RunContext:
    source: str
    run_id: str
    staging_root: Path
    fetch_policy: FetchPolicy = "default"
    input_path: Path | None = None  # local-file mode

    @property
    def source_dir(self) -> Path:
        return self.staging_root / self.source

    @property
    def run_dir(self) -> Path:
        return self.source_dir / self.run_id

    @property
    def raw_dir(self) -> Path:
        return self.run_dir / "raw"

    @property
    def records_path(self) -> Path:
        return self.run_dir / "records.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    @property
    def cache_dir(self) -> Path:
        return self.source_dir / "cache"

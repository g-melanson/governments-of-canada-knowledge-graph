from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SilverInput:
    source: str
    silver_run_id: str

    def fragments_path(self, silver_root: Path) -> Path:
        return silver_root / self.source / self.silver_run_id / "fragments.jsonl"

    def manifest_path(self, silver_root: Path) -> Path:
        return silver_root / self.source / self.silver_run_id / "manifest.json"


@dataclass(frozen=True)
class IntegrateContext:
    run_id: str
    inputs: tuple[SilverInput, ...]
    silver_root: Path = Path("silver")
    bronze_root: Path = Path("bronze")
    resolver: str = "integrate.resolvers.identity.get_resolver"
    members_bronze_path: Path | None = None
    expenditures_bronze_path: Path | None = None
    person_crosswalk_tsv: Path | None = None

    @property
    def merged_dir(self) -> Path:
        return self.silver_root / "merged" / self.run_id

    @property
    def nodes_path(self) -> Path:
        return self.merged_dir / "nodes.jsonl"

    @property
    def edges_path(self) -> Path:
        return self.merged_dir / "edges.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.merged_dir / "manifest.json"

    @property
    def resolution_report_path(self) -> Path:
        return self.merged_dir / "resolution_report.json"

    @property
    def quarantine_path(self) -> Path:
        return self.merged_dir / "quarantine.jsonl"

    def sorted_inputs(self) -> tuple[SilverInput, ...]:
        return tuple(sorted(self.inputs, key=lambda i: (i.source, i.silver_run_id)))


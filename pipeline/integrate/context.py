from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pipeline.paths import UniversePaths


@dataclass(frozen=True)
class SilverInput:
    source: str
    silver_run_id: str


@dataclass(frozen=True)
class IntegrateContext:
    run_id: str
    inputs: tuple[SilverInput, ...]
    paths: UniversePaths = field(default_factory=UniversePaths)
    resolver: str = "integrate.resolvers.identity.get_resolver"
    members_bronze_path: Path | None = None
    expenditures_bronze_path: Path | None = None
    person_crosswalk_tsv: Path | None = None

    @property
    def merged_dir(self) -> Path:
        return self.paths.merged_run_dir(self.run_id)

    @property
    def nodes_path(self) -> Path:
        return self.paths.merged_nodes(self.run_id)

    @property
    def edges_path(self) -> Path:
        return self.paths.merged_edges(self.run_id)

    @property
    def manifest_path(self) -> Path:
        return self.paths.merged_manifest(self.run_id)

    @property
    def resolution_report_path(self) -> Path:
        return self.paths.merged_resolution_report(self.run_id)

    @property
    def quarantine_path(self) -> Path:
        return self.paths.merged_quarantine(self.run_id)

    def sorted_inputs(self) -> tuple[SilverInput, ...]:
        return tuple(sorted(self.inputs, key=lambda i: (i.source, i.silver_run_id)))

    def fragments_path(self, inp: SilverInput) -> Path:
        return self.paths.silver_fragments(inp.source, inp.silver_run_id)

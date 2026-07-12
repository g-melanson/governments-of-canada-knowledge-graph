"""Merge engine for Stage 4 integrate."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from pipeline.integrate.resolvers.base import EntityResolver
from pipeline.integrate.errors import (
    FragmentShapeError, 
    MergeConflictError, 
    SilverInputError
    )

RESERVED_NODE_KEYS = frozenset({
    "@type", "id", "subject", "object", "predicate", "rel_type",
    "bronze_reference", "bronze_references", "sources",
})
RESERVED_EDGE_KEYS = RESERVED_NODE_KEYS  # edges use the same reserved set


@dataclass
class MergeSummary:
    input_fragment_count: int = 0
    input_node_count: int = 0
    input_edge_count: int = 0
    merged_node_count: int = 0
    merged_edge_count: int = 0
    node_merges: int = 0
    edge_merges: int = 0
    conflicts: int = 0
    quarantined: int = 0


def iter_fragments(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise SilverInputError(f"Silver fragments not found: {path}")
    with path.open(encoding="utf-8") as fin:
        for line_number, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            yield line_number, json.loads(line)


def is_edge(fragment: dict[str, Any]) -> bool:
    return "subject" in fragment and "object" in fragment


def normalize_predicate(fragment: dict[str, Any]) -> str:
    predicate = fragment.get("predicate")
    if predicate:
        return str(predicate)
    rel_type = fragment.get("rel_type")
    if rel_type:
        return str(rel_type)
    raise FragmentShapeError(f"edge missing predicate and rel_type: {fragment}")


def normalize_edge_endpoints(fragment: dict[str, Any]) -> tuple[str, str, str]:
    subject = fragment.get("subject")
    obj = fragment.get("object")
    predicate = normalize_predicate(fragment)
    if not (subject and obj):
        raise FragmentShapeError(f"malformed edge endpoints: {fragment}")
    return str(subject), predicate, str(obj)


def edge_merge_key(
    fragment: dict[str, Any], subject: str, predicate: str, obj: str
) -> tuple:
    edge_id = fragment.get("id")
    if edge_id:
        return ("id", str(edge_id))
    return ("triple", fragment.get("@type") or "RELATIONSHIP", subject, predicate, obj)


def _ref_key(ref: dict[str, Any]) -> tuple:
    return (ref.get("source"), ref.get("bronze_run_id"), ref.get("line_number"))


def _refs(fragment: dict[str, Any]) -> list[dict[str, Any]]:
    ref = fragment.get("bronze_reference")
    return [ref] if ref else list(fragment.get("bronze_references") or [])


def _merge_attrs(existing: dict[str, Any], incoming: dict[str, Any], reserved: frozenset[str]) -> dict[str, list[Any]]:
    """Return newly discovered conflicting alternates (slot -> values)."""
    alternates: dict[str, list[Any]] = {}
    for key, value in incoming.items():
        if key in reserved or value in (None, "", "None"):
            continue
        if key not in existing or existing[key] in (None, "", "None"):
            existing[key] = value
            continue
        if existing[key] != value:
            alternates.setdefault(key, sorted({existing[key], value}, key=str))
    return alternates


@dataclass
class GraphAccumulator:
    resolver: EntityResolver
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[tuple, dict[str, Any]] = field(default_factory=dict)
    summary: MergeSummary = field(default_factory=MergeSummary)
    resolution: dict[str, set[str]] = field(default_factory=dict)
    attribute_alternates: dict[str, dict[str, list[Any]]] = field(default_factory=dict)

    def add_node(self, fragment: dict[str, Any], source: str, silver_run_id: str) -> None:
        node_id = fragment.get("id")
        if not node_id:
            raise FragmentShapeError("node missing id")

        node_type = fragment.get("@type")
        cid = self.resolver.canonical_id(str(node_id), node_type=node_type)
        attrs = {k: v for k, v in fragment.items() if k not in RESERVED_NODE_KEYS}

        existing = self.nodes.get(cid)
        if existing is None:
            self.nodes[cid] = {
                "@type": node_type,
                "id": cid,
                **attrs,
                "labels": set(fragment.get("labels") or []),
                "bronze_references": {_ref_key(r): r for r in _refs(fragment)},
                "sources": {(source, silver_run_id)},
            }
        else:
            if existing["@type"] != node_type:
                self.summary.conflicts += 1
                raise MergeConflictError(
                    f"@type conflict for {cid}: {existing['@type']} vs {node_type}"
                )
            alts = _merge_attrs(existing, fragment, RESERVED_NODE_KEYS)
            if alts:
                self.attribute_alternates.setdefault(cid, {}).update(alts)
            existing["labels"].update(fragment.get("labels") or [])
            for r in _refs(fragment):
                existing["bronze_references"].setdefault(_ref_key(r), r)
            existing["sources"].add((source, silver_run_id))
            self.summary.node_merges += 1

        self.resolution.setdefault(cid, set()).add(str(node_id))

    def add_edge(self, fragment: dict[str, Any], source: str, silver_run_id: str) -> None:
        subject, predicate, obj = normalize_edge_endpoints(fragment)
        subject = self.resolver.resolve_endpoint(subject)
        obj = self.resolver.resolve_endpoint(obj)
        key = edge_merge_key(fragment, subject, predicate, obj)
        edge_type = fragment.get("@type") or "RELATIONSHIP"
        attrs = {k: v for k, v in fragment.items() if k not in RESERVED_EDGE_KEYS}

        existing = self.edges.get(key)
        if existing is None:
            self.edges[key] = {
                "@type": edge_type,
                "id": fragment.get("id"),
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                **attrs,
                "bronze_references": {_ref_key(r): r for r in _refs(fragment)},
                "sources": {(source, silver_run_id)},
            }
        else:
            alts = _merge_attrs(existing, fragment, RESERVED_EDGE_KEYS)
            edge_id = fragment.get("id")
            if edge_id and not existing.get("id"):
                existing["id"] = edge_id
            alt_key = f"edge:{key!r}"
            if alts:
                self.attribute_alternates.setdefault(alt_key, {}).update(alts)
            for r in _refs(fragment):
                existing["bronze_references"].setdefault(_ref_key(r), r)
            existing["sources"].add((source, silver_run_id))
            self.summary.edge_merges += 1
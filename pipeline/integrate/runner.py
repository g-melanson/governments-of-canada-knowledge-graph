"""Orchestrate Stage 4 integrate → merged Silver."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from pipeline.integrate.resolvers.base import EntityResolver
from pipeline.integrate.context import IntegrateContext
from pipeline.integrate.engine import (
    GraphAccumulator, 
    is_edge, 
    iter_fragments
    )
from pipeline.integrate.errors import (
    EmptyMergeError, 
    FragmentShapeError, 
    MergeConflictError
    )

log = logging.getLogger(__name__)


def _load_resolver(dotted_path: str, ctx: IntegrateContext) -> EntityResolver:
    import importlib
    import inspect

    module_path, fn_name = dotted_path.rsplit(".", 1)
    factory = getattr(importlib.import_module(module_path), fn_name)
    params = inspect.signature(factory).parameters
    if len(params) >= 1:
        return factory(ctx)
    return factory()


def _quarantine_entry(
    *, source: str, silver_run_id: str, line: int, fragment: dict, reason: str, error: str = ""
) -> dict:
    return {
        "source": source,
        "silver_run_id": silver_run_id,
        "line": line,
        "reason": reason,
        "error": error,
        "fragment": fragment,
    }


def run_integrate(ctx: IntegrateContext) -> dict:
    ctx.merged_dir.mkdir(parents=True, exist_ok=True)
    resolver = _load_resolver(ctx.resolver, ctx)
    acc = GraphAccumulator(resolver)
    quarantine: list[dict] = []
    conflicts: list[dict] = []
    started_at = datetime.now(timezone.utc)

    for inp in ctx.sorted_inputs():
        path = ctx.fragments_path(inp)
        for line_number, fragment in iter_fragments(path):
            acc.summary.input_fragment_count += 1
            try:
                if is_edge(fragment):
                    acc.summary.input_edge_count += 1
                    acc.add_edge(fragment, inp.source, inp.silver_run_id)
                elif fragment.get("id"):
                    acc.summary.input_node_count += 1
                    acc.add_node(fragment, inp.source, inp.silver_run_id)
                else:
                    raise FragmentShapeError("unclassifiable or null-id fragment")
            except MergeConflictError as e:
                acc.summary.conflicts += 1
                entry = _quarantine_entry(
                    source=inp.source,
                    silver_run_id=inp.silver_run_id,
                    line=line_number,
                    fragment=fragment,
                    reason="type_conflict",
                    error=str(e),
                )
                quarantine.append(entry)
                conflicts.append(entry)
            except FragmentShapeError as e:
                acc.summary.quarantined += 1
                quarantine.append(
                    _quarantine_entry(
                        source=inp.source,
                        silver_run_id=inp.silver_run_id,
                        line=line_number,
                        fragment=fragment,
                        reason="fragment_shape",
                        error=str(e),
                    )
                )

    acc.summary.merged_node_count = len(acc.nodes)
    acc.summary.merged_edge_count = len(acc.edges)

    if acc.summary.merged_node_count == 0 and acc.summary.merged_edge_count == 0:
        raise EmptyMergeError("no nodes or edges survived integration")

    _write_nodes(ctx, acc)
    _write_edges(ctx, acc)

    if quarantine:
        with ctx.quarantine_path.open("w", encoding="utf-8") as fq:
            for entry in quarantine:
                fq.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if conflicts:
        with (ctx.merged_dir / "conflicts.jsonl").open("w", encoding="utf-8") as fc:
            for entry in conflicts:
                fc.write(json.dumps(entry, ensure_ascii=False) + "\n")

    finished_at = datetime.now(timezone.utc)
    manifest = _build_manifest(ctx, acc, started_at, finished_at, len(quarantine), len(conflicts))
    ctx.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_resolution_report(ctx, acc)

    log.info(
        "integrate_complete run_id=%s nodes=%s edges=%s quarantined=%s",
        ctx.run_id,
        acc.summary.merged_node_count,
        acc.summary.merged_edge_count,
        acc.summary.quarantined,
    )
    return manifest


def _serialize_node(node: dict) -> dict:
    out: dict = {"@type": node["@type"], "id": node["id"]}
    for key, value in sorted(node.items()):
        if key in RESERVED_NODE_KEYS or key in {"labels", "bronze_references", "sources"}:
            continue
        if value not in (None, "", "None"):
            out[key] = value
    if node.get("labels"):
        out["labels"] = sorted(node["labels"])
    out["bronze_references"] = sorted(
        node["bronze_references"].values(),
        key=lambda r: (r.get("source", ""), r.get("bronze_run_id", ""), r.get("line_number", 0)),
    )
    out["sources"] = [{"source": s, "silver_run_id": r} for s, r in sorted(node["sources"])]
    return out


def _serialize_edge(edge: dict) -> dict:
    out: dict = {
        "@type": edge["@type"],
        "subject": edge["subject"],
        "predicate": edge["predicate"],
        "object": edge["object"],
    }
    if edge.get("id"):
        out["id"] = edge["id"]
    for key, value in sorted(edge.items()):
        if key in RESERVED_EDGE_KEYS or key in {"bronze_references", "sources"}:
            continue
        if value not in (None, "", "None"):
            out[key] = value
    out["bronze_references"] = sorted(
        edge["bronze_references"].values(),
        key=lambda r: (r.get("source", ""), r.get("bronze_run_id", ""), r.get("line_number", 0)),
    )
    out["sources"] = [{"source": s, "silver_run_id": r} for s, r in sorted(edge["sources"])]
    return out


RESERVED_NODE_KEYS = frozenset({
    "@type", "id", "subject", "object", "predicate", "rel_type",
    "bronze_reference", "bronze_references", "sources", "labels",
})
RESERVED_EDGE_KEYS = RESERVED_NODE_KEYS


def _write_nodes(ctx: IntegrateContext, acc: GraphAccumulator) -> None:
    with ctx.nodes_path.open("w", encoding="utf-8") as fout:
        for nid in sorted(acc.nodes):
            fout.write(json.dumps(_serialize_node(acc.nodes[nid]), ensure_ascii=False) + "\n")


def _write_edges(ctx: IntegrateContext, acc: GraphAccumulator) -> None:
    with ctx.edges_path.open("w", encoding="utf-8") as fout:
        for key in sorted(acc.edges):
            fout.write(json.dumps(_serialize_edge(acc.edges[key]), ensure_ascii=False) + "\n")


def _build_manifest(ctx, acc, started_at, finished_at, quarantine_count, conflict_count) -> dict:
    s = acc.summary
    return {
        "run_id": ctx.run_id,
        "stage": "integrate",
        "tier": "silver-merged",
        "resolver": ctx.resolver,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success",
        "inputs": [
            {
                "source": i.source,
                "silver_run_id": i.silver_run_id,
                "fragments_path": str(ctx.fragments_path(i)),
            }
            for i in ctx.sorted_inputs()
        ],
        "output": {
            "nodes_path": str(ctx.nodes_path),
            "edges_path": str(ctx.edges_path),
            "quarantine_path": str(ctx.quarantine_path),
            "input_fragment_count": s.input_fragment_count,
            "input_node_count": s.input_node_count,
            "input_edge_count": s.input_edge_count,
            "merged_node_count": s.merged_node_count,
            "merged_edge_count": s.merged_edge_count,
            "node_merges": s.node_merges,
            "edge_merges": s.edge_merges,
            "quarantine_count": quarantine_count,
            "conflict_count": conflict_count,
        },
    }


def _write_resolution_report(ctx: IntegrateContext, acc: GraphAccumulator) -> None:
    merges = {
        cid: sorted(originals)
        for cid, originals in acc.resolution.items()
        if len(originals) > 1 or (originals and next(iter(originals)) != cid)
    }
    report = {
        "run_id": ctx.run_id,
        "resolver": ctx.resolver,
        "merged_groups": merges,
        "attribute_alternates": acc.attribute_alternates,
        "node_merges": acc.summary.node_merges,
        "edge_merges": acc.summary.edge_merges,
        "conflicts": acc.summary.conflicts,
        "quarantined": acc.summary.quarantined,
    }
    ctx.resolution_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

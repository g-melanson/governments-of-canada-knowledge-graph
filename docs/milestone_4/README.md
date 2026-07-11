# Milestone 4 — Integrate pipeline (Stage 4 / Silver merged)

**Goal:** Merge per-source **Silver graph fragments** into a single reconciled graph under `silver/merged/{run_id}/`, deduplicating nodes and edges by GCKG URI, preserving provenance and reified edge metadata, and resolving cross-source entities where rules exist.

**As implemented:** the `integrate/` package reads one or more Silver runs, classifies fragments as nodes or edges, applies an `EntityResolver`, merges by canonical URI, and writes deterministic `nodes.jsonl` / `edges.jsonl` plus manifest, resolution report, and quarantine. No new third-party dependency.

| Stage | Tier | Package | CLI |
|-------|------|---------|-----|
| 4 — Integrate | Silver (merged) | `integrate/` | `python -m integrate run …` |

**Execution plan:** [`integrate-execution-plan.md`](integrate-execution-plan.md)

**Prerequisite:** At least one completed Stage 3 run per source under `silver/{source}/{run_id}/`.

## Resolvers

| Resolver | Factory | Purpose |
|----------|---------|---------|
| `IdentityResolver` (default) | `integrate.resolvers.identity.get_resolver` | Exact-URI merge |
| `CommonsPersonResolver` | `integrate.resolvers.commons_person.get_resolver` | Map expenditure Person stubs → members Person URIs via Bronze crosswalk |

Use `--members-bronze`, `--expenditures-bronze`, or `--person-crosswalk-tsv` when running `commons_person`.

## Output layout

```text
silver/merged/{run_id}/
  nodes.jsonl
  edges.jsonl
  manifest.json
  resolution_report.json
  quarantine.jsonl          # shape errors, null ids, conflicts
```

**Neo4j dev shortcut:** `tools/neo4j_import/preprocess_silver.py` can load single-source Silver directly — acceptable for per-source dev; multi-source graphs require `silver/merged/`.

## Done criteria

- [x] `integrate/` package: CLI, runner, engine, context, errors
- [x] Node merge by canonical GCKG URI with provenance union
- [x] Edge normalize (`rel_type` → `predicate`) and dedupe
- [x] Deterministic, idempotent merged output
- [x] `EntityResolver` hook with identity default
- [x] `CommonsPersonResolver` for members ↔ expenditures Person resolution
- [x] `integrate/tests/` with crosswalk fixtures
- [ ] Full integration test against production-scale Silver runs in CI
- [ ] Additional cross-source rules (Agent dedupe, PoliticalParty by label) — deferred

## Handoff to Stage 5

```bash
python -m publish run --merged-run-id {run_id}-merged --run-id {run_id}
```

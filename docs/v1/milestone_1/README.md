# Milestone 1 — Ingestion pipeline (Stage 1)

**Goal:** Parse raw publisher data into source-shaped `records.jsonl` and a provenance `manifest.json` under `staging/`.

**Status:** Done for three House of Commons sources. Normalization is centralized in `ingest/normalize.py` (`SchemaNormalizer`), driven by LinkML slot ranges. Adapters tag each row with `_row_class` for multi-class sources.

| Stage | Tier | Package | CLI |
|-------|------|---------|-----|
| 1 — Ingest | — | `ingest/` | `python -m ingest run …` |

**Diagrams:** [`gckg.mmd`](gckg.mmd) · [`gckg-sources.mmd`](gckg-sources.mmd)

**Execution plan (historical build guide):** [`commons-members-execution-plan.md`](commons-members-execution-plan.md)

**Adapter refactor guide:** [`../ingest-adapter-refactor-guide.md`](../ingest-adapter-refactor-guide.md)

## Registered sources

```bash
python -m ingest list-sources
# commons_members
# commons_members_bylaw
# commons_members_expenditures
```

| Source | Module | Fetch | Notes |
|--------|--------|-------|-------|
| `commons_members` | `ingest/adapters/commons/members.py` | HTTP or `local-file` | MP XML |
| `commons_members_bylaw` | `ingest/adapters/commons/members_bylaw.py` | HTTP or `local-file` | Bylaw XML; multi-class rows |
| `commons_members_expenditures` | `ingest/adapters/commons/members_expenditures.py` | `local-file` only | Pickle corpus at `data/expense_claims.pkl` |

## Output layout

```text
staging/{source}/{run_id}/
  raw/{filename}
  records.jsonl
  manifest.json
```

## Done criteria

- [x] Ingest platform: CLI, registry, fetch policies, staging layout
- [x] Three Commons adapters + unit tests (`ingest/tests/adapters/`)
- [x] Schema-driven normalization via `SchemaNormalizer`
- [x] No GCKG domain IDs in Stage 1 output
- [ ] `run-all` orchestration across sources
- [ ] Additional adapters (Open Canada, Justice, UDC) — deferred

## Handoff to Stage 2

```bash
python -m validate run --source commons_members --staging-run-id {run_id} --run-id {run_id}
```

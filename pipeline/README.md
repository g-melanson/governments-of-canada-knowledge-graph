# GCKG pipeline

Five-stage medallion pipeline: ingest → validate → transform → integrate → publish.

Runtime output lives under **`universe/`** (gitignored). Path geometry is centralized in [`paths.py`](paths.py) (`UniversePaths`). Every stage accepts `--universe-root` (default: `universe`).

## Stages

| Stage | Directory | CLI | Input → output |
|-------|-----------|-----|----------------|
| 1 — Ingest | [`ingest/`](ingest/) | `python3 -m pipeline.ingest` | Publisher raw → `universe/{run_id}/1-staging/{source}/` |
| 2 — Validate | [`validate/`](validate/) | `python3 -m pipeline.validate` | Staging → `universe/{run_id}/2-bronze/{source}/` + quarantine |
| 3 — Transform | [`transforms/`](transforms/) | `python3 -m pipeline.transforms` | Bronze → `universe/{run_id}/3-silver/{source}/` |
| 4 — Integrate | [`integrate/`](integrate/) | `python3 -m pipeline.integrate` | Silver → `universe/{run_id}/4-merged/` |
| 5 — Publish | [`publish/`](publish/) | `python3 -m pipeline.publish` | Merged → `universe/{run_id}/5-gold/` |

## Repository layout (code)

```text
pipeline/           Stage runners (this tree)
sources/            Per-source adapter, source schema, transform map
schemas/            Domain LinkML (Gold validation gate)
universe/           Runtime output (gitignored)
```

## Universe output layout

Each E2E run is grouped under one directory:

```text
universe/
  {run_id}/
    1-staging/{source}/
      raw/              publisher snapshot
      records.jsonl
      manifest.json
    2-bronze/{source}/
      records.jsonl
      manifest.json
    3-silver/{source}/
      fragments.jsonl
      quarantine.jsonl
      manifest.json
    4-merged/
      nodes.jsonl
      edges.jsonl
      manifest.json
      resolution_report.json
      quarantine.jsonl
    5-gold/
      nodes.jsonl
      edges.jsonl
      manifest.json
      quarantine/
    quarantine/{source}/    validate rejects + drift_report.json
  cache/{source}/           shared HTTP fetch cache (not per-run)
```

## End-to-end example

Use one `RUN_ID` across all stages. From repo root with venv active (`pip install -e ".[dev,validate]"`):

```bash
rm -rf universe/
RUN_ID=$(date -u +%Y-%m-%dT%H%M%SZ)

# Stage 1 — Ingest (fixtures for members/bylaw; expenditures uses data/expense_claims.pkl)
python3 -m pipeline.ingest run --source commons_members \
  --run-id "$RUN_ID" --fetch-policy local-file \
  --input pipeline/ingest/tests/fixtures/raw/commons_members_sample.xml

python3 -m pipeline.ingest run --source commons_members_bylaw \
  --run-id "$RUN_ID" --fetch-policy local-file \
  --input pipeline/ingest/tests/fixtures/raw/commons_members_bylaw_sample.xml

python3 -m pipeline.ingest run --source commons_members_expenditures \
  --run-id "$RUN_ID"

# Stage 2 — Validate
for src in commons_members commons_members_bylaw commons_members_expenditures; do
  python3 -m pipeline.validate run --source "$src" --run-id "$RUN_ID"
done

# Stage 3 — Transform
for src in commons_members commons_members_bylaw commons_members_expenditures; do
  python3 -m pipeline.transforms run --source "$src" --run-id "$RUN_ID"
done

# Stage 4 — Integrate (commons_person resolver for members ↔ expenditures)
python3 -m pipeline.integrate run \
  --run-id "$RUN_ID" \
  --resolver pipeline.integrate.resolvers.commons_person.get_resolver \
  --input commons_members \
  --input commons_members_bylaw \
  --input commons_members_expenditures

# Stage 5 — Publish
python3 -m pipeline.publish run --run-id "$RUN_ID"
```

For live HTTP ingest on members/bylaw, replace `--fetch-policy local-file --input …` with `--fetch-policy refresh`.

## Diagrams

- [`diagrams/pipeline.mmd`](diagrams/pipeline.mmd) — stage flow
- [`diagrams/sources.mmd`](diagrams/sources.mmd) — source families (target architecture)

## Design principles

- **Schema-first** — LinkML contracts in `sources/` (Bronze) and `schemas/` (Gold).
- **Fail-fast gates** — Validate at Bronze and Gold; rejects go to quarantine.
- **Provenance** — Manifests at every tier; `bronze_reference` on Silver fragments.
- **Reproducible runs** — One `run_id` directory holds every stage of a pipeline execution.

## Tests

```bash
python3 -m pytest pipeline/ingest/tests pipeline/validate/tests \
  pipeline/transforms/tests pipeline/integrate/tests
```

# Milestone 5 — Publish pipeline (Stage 5 / Gold)

**Goal:** Validate merged Silver nodes and edges against the LinkML **domain schema** (`domain_model/schema.yaml`) and write **Gold** output suitable for downstream graph databases and query layers.

**As implemented:** the `publish/` package streams `silver/merged/{merged_run_id}/nodes.jsonl` and `edges.jsonl`, strips provenance keys before validation, and routes domain-invalid fragments to Gold quarantine.

| Stage | Tier | Package | CLI |
|-------|------|---------|-----|
| 5 — Publish | Gold | `publish/` | `python -m publish run …` |

**Prerequisite:** A completed Stage 4 run under `silver/merged/{merged_run_id}/`.

## How it works

1. Read merged Silver `nodes.jsonl` and `edges.jsonl`.
2. Strip provenance keys (`bronze_references`, `sources`, `bronze_reference`, …).
3. Validate each fragment's `@type` against `domain_model/schema.yaml` with `linkml.validator.Validator`.
4. Write accepted fragments to `gold/{run_id}/` and rejects to `gold/{run_id}/quarantine/`.

## Output layout

```text
gold/{run_id}/
  nodes.jsonl
  edges.jsonl
  manifest.json
  quarantine/
    nodes.jsonl
    edges.jsonl
```

## Neo4j export

For loading into Neo4j, see [`../sop_silver_to_neo4j.md`](../sop_silver_to_neo4j.md) and `tools/neo4j_import/`.

## Done criteria

- [x] `publish/` package: CLI, runner, engine, context
- [x] Domain validation gate on merged Silver
- [x] Accepted → `gold/`; rejected → quarantine with error detail
- [x] `publish` console script wired in `pyproject.toml`
- [ ] `publish/tests/` with offline fixtures (referenced in `pyproject.toml` but not yet present)
- [ ] Publish drift report format aligned with Bronze quarantine reports

## Example

```bash
python -m publish run --merged-run-id 2026-07-08T145010Z-merged --run-id demo
```

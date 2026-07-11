# Milestone 2 — Validate pipeline (Stage 2 / Bronze)

**Goal:** Validate Stage 1 `records.jsonl` against LinkML **source schemas**, write **Bronze** (source-validated records), and route failures to **quarantine** with a drift report.

**Status:** Done for all three Commons sources. Uses `linkml.validator.Validator` (JSON Schema plugin, closed world). Catalog validation and progress logging for very large files remain partial.

| Stage | Tier | Package | CLI |
|-------|------|---------|-----|
| 2 — Validate | Bronze | `validate/` | `python -m validate run …` |

**Execution plan (historical build guide):** [`validate-execution-plan.md`](validate-execution-plan.md)

## Validatable sources

```bash
python -m validate list-sources
# commons_members
# commons_members_bylaw
# commons_members_expenditures
```

| Source | Schema | Target class |
|--------|--------|--------------|
| `commons_members` | `source/commons_members.schema.yaml` | `CommonsMembersRow` |
| `commons_members_bylaw` | `source/commons_members_bylaw.schema.yaml` | `ByLawDocumentRow` (+ section/paragraph classes) |
| `commons_members_expenditures` | `source/commons_members_expenditures.schema.yaml` | `ExpenseReportRow` (+ claim row classes) |

## Output layout

```text
bronze/{source}/{run_id}/records.jsonl + manifest.json
quarantine/{source}/{run_id}/rejects.jsonl + drift_report.json   (if any rejects)
```

Bronze records are identical to accepted staging rows — no domain IDs, no transform.

## Done criteria

- [x] `validate/` package with CLI, runner, engine, tests
- [x] Source schemas for all three Commons sources
- [x] Staging → Bronze with quarantine on reject
- [x] `--fail-fast` supported
- [ ] Catalog validation (ingest sources ∩ schema registry) at startup
- [ ] Progress logging for multi-million-row JSONL files
- [ ] Open Canada contributions validation — deferred (no source schema)

## Handoff to Stage 3

```bash
python -m transforms run --source commons_members --bronze-run-id {run_id} --run-id {run_id}
```

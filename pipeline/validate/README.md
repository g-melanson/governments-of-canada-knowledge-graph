# Stage 2 — Validate

LinkML validation gate: read staging JSONL, write **Bronze** (accepted rows identical to staging), route rejects to **quarantine** with a drift report.

| | |
|--|--|
| **CLI** | `python3 -m pipeline.validate` |
| **Tier** | Bronze |
| **Input** | `universe/{run_id}/1-staging/{source}/` |
| **Output** | `universe/{run_id}/2-bronze/{source}/` + `universe/{run_id}/quarantine/{source}/` |

## Commands

```bash
python3 -m pipeline.validate list-sources

python3 -m pipeline.validate run \
  --source commons_members \
  --run-id demo

# CI schema drift: stop on first invalid row
python3 -m pipeline.validate run \
  --source commons_members \
  --run-id demo \
  --fail-fast
```

### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--source` | required | Source name |
| `--run-id` | UTC timestamp | Run directory under `universe/` |
| `--staging-run-id` | same as `--run-id` | Override staging input when it differs |
| `--universe-root` | `universe` | Runtime output root |
| `--fail-fast` | off | Stop on first rejected row |

## Validatable sources

Configured in [`config/schemas.yaml`](config/schemas.yaml):

| Source | Schema | Primary class |
|--------|--------|---------------|
| `commons_members` | `sources/commons_members/commons_members.schema.yaml` | `CommonsMembersRow` |
| `commons_members_bylaw` | `sources/commons_members_bylaw/commons_members_bylaw.schema.yaml` | `ByLawDocumentRow` (+ section/paragraph classes) |
| `commons_members_expenditures` | `sources/commons_members_expenditures/commons_members_expenditures.schema.yaml` | `ExpenseReportRow` (+ claim row classes) |

Validation uses `linkml.validator.Validator` (JSON Schema plugin, closed world).

## Output layout

```text
universe/{run_id}/2-bronze/{source}/
  records.jsonl
  manifest.json

universe/{run_id}/quarantine/{source}/     (only if rejects exist)
  rejects.jsonl
  drift_report.json
```

**Invariant:** Bronze records are byte-identical to accepted staging rows — no transform, no domain IDs.

## Package layout

```text
validate/
  cli.py
  runner.py
  engine.py          streaming validate_records()
  context.py         ValidateContext → UniversePaths
  config/schemas.yaml
  tests/
```

## Handoff to Stage 3

```bash
python3 -m pipeline.transforms run \
  --source commons_members \
  --run-id {run_id}
```

# Spec: BARRED-Fleet Fresh Cloud Debate

## Assumptions

1. This is the next post-submission engineering slice, not a required pre-submission change.
2. The first implementation must be synchronous, tiny, and budget-bounded.
3. The first implementation should prove fresh cloud execution without also implementing full Firestore writes, GCS uploads, async queues, Agent Gateway, Model Armor, or reflection.
4. The existing curated run-reporting path must remain unchanged and keep passing `make verify-demo`.
5. Live model calls are opt-in only and must be disabled by default.

If any of these are wrong, revise this spec before implementing.

## Objective

Add a minimal fresh debate execution path to BARRED-Fleet so the Cloud Run service can execute one small debate case instead of only reporting a pre-existing curated run.

Current shipped flow:

```text
run ID → Firestore metadata → private GCS artifacts → deterministic B-gate → ADK narration
```

First fresh-execution slice:

```text
POST /runs/fresh-demo
  → validate one seed/config
  → run a tiny fresh debate with strict limits
  → write temporary artifacts under /tmp
  → run deterministic B-gate/report assembly
  → return report JSON
```

This slice proves fresh cloud debate execution while keeping persistence, async orchestration, and production hardening separate.

## Artifact Promotion And Reporting Slice

Fresh runs initially write artifacts under the Cloud Run instance `/tmp`
filesystem. That proves execution, but `/tmp` is ephemeral and not externally
auditable after the instance is replaced. The next reporting slice therefore
adds a deterministic promotion decision without yet uploading artifacts:

```text
fresh runner result
  → resolve artifact paths under the fresh run directory only
  → summarize attempts/checkpoint/record/cassette artifacts
  → run B-gate when an accepted corpus exists
  → return fresh_report.promotion
```

Promotion states after the durable writer slice:

- `not_promoted/missing_input_artifact`: no accepted corpus was produced, so
  there is nothing safe to promote.
- `not_promoted/b_gate_not_passed`: a corpus exists, but deterministic B-gate
  failed.
- `ready/promotion_disabled`: B-gate passed, but cloud writes are disabled.
- `ready/promotion_bucket_missing`: cloud writes are enabled, but no destination
  GCS bucket URI is configured.
- `ready/firestore_collection_missing`: cloud writes are enabled, but no
  Firestore registry collection is configured.
- `not_promoted/promotion_failed`: GCS or Firestore returned an error; the run
  response remains structured instead of failing with a server error.
- `promoted/gcs_and_firestore_written`: existing fresh-run artifacts were copied
  to GCS and the Firestore run registry was updated.

The promotion report is intentionally conservative. It must not claim durable
GCS/Firestore provenance unless `BARRED_PROMOTE_FRESH_RUNS=true`, B-gate passes,
and both the GCS upload and Firestore registry write complete.

When B-gate passes, the fresh reporter also writes a deterministic receipt:

```json
{
  "summary_metrics": [
    {
      "metric_name": "fresh_b_gate_contract",
      "num_cases_total": 1,
      "num_cases_valid": 1,
      "num_cases_error": 0,
      "mean_score": 1.0,
      "fixture_run_id": "<run_id>",
      "accepted_rows": 1,
      "total_rows": 1,
      "verifier_parse_ok_rate": 1.0,
      "verifier_pass_rate": 1.0,
      "anchor_match_rate": 1.0
    }
  ]
}
```

This is not a synthetic LLM grade. It is a deterministic receipt that mirrors the
B-gate facts already computed for the fresh run, so the promoted run can satisfy
the same report contract as curated runs.

Promotion configuration:

```text
BARRED_PROMOTE_FRESH_RUNS=true
BARRED_FRESH_PROMOTION_BUCKET=gs://<bucket-or-prefix>
BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION=<collection>
BARRED_RUN_REGISTRY_FIRESTORE_PROJECT=<project>
BARRED_RUN_REGISTRY_FIRESTORE_DATABASE=<database>
```

The Firestore payload uses the same artifact keys that
`report_barred_run(run_id=...)` already resolves: `input_path`, `attempts_path`,
`checkpoint_path`, `record_path`, `cassette_path`, `deterministic_eval_result_path`,
and `min_verifier_parse_ok_rate`.

## Tech Stack

- Python `>=3.11`
- FastAPI route inside `barred-fleet/app/fast_api_app.py`
- Google ADK tool surface in `barred-fleet/app/tools.py`
- Existing debate runner logic under `scenarios/debate/`
- Existing deterministic B-gate/report code reused by `report_barred_run`
- Cloud Run runtime with `/tmp` artifact storage
- Existing model routes from demo artifacts:
  - generation/debate lane: `ollama/gemma4:31b-cloud`
  - judge/verifier lane: `ollama/gpt-oss:120b-cloud`

No new cloud service is introduced in this first slice.

## Commands

Baseline before implementation:

```bash
cd barred-fleet
make verify-demo
make test-unit
```

Target local tests after implementation:

```bash
cd barred-fleet
uv run pytest tests/unit/test_fresh_debate.py -q
uv run pytest tests/unit/test_tools.py tests/unit/test_demo.py tests/unit/test_run_registry.py -q
```

Target deployed manual smoke after explicit approval:

```bash
cd barred-fleet
agents-cli deploy \
  --project gem-creation \
  --region us-east1 \
  --service-account barred-fleet-runtime@gem-creation.iam.gserviceaccount.com \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 1 \
  --no-confirm-project
```

Authenticated fresh-run smoke:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "https://barred-fleet-837262597425.us-east1.run.app/runs/fresh-demo" \
  -d '{
    "seed_id": "fixture:first",
    "dry_run": true,
    "max_attempts": 1
  }'
```

The first live model run must use:

```json
{
  "seed_id": "fixture:first",
  "dry_run": false,
  "max_attempts": 1,
  "timeout_seconds": 180
}
```

Only run live mode after explicitly confirming budget.

## Project Structure

```text
barred-fleet/app/fresh_debate.py
  New small module for request validation, run-id creation, temp artifact paths, dry-run planning, and runner orchestration.

barred-fleet/app/fast_api_app.py
  Adds POST /runs/fresh-demo.

barred-fleet/app/tools.py
  May expose a new ADK tool function run_fresh_debate_case(...), but report_barred_run(...) must remain unchanged.

barred-fleet/tests/unit/test_fresh_debate.py
  Unit tests for disabled mode, dry-run mode, request validation, temp artifact planning, and fake-runner success.

barred-fleet/tests/fixtures/fresh_debate/
  Tiny fixture seed and fake runner outputs if needed.

docs/SPEC_BARRED_FLEET_FRESH_CLOUD_DEBATE.md
  This spec.
```

Avoid adding production Firestore/GCS write modules in this slice. Those belong to later specs.

## API Contract

### Route

```text
POST /runs/fresh-demo
```

### Request

```json
{
  "seed_id": "fixture:first",
  "run_id": "",
  "dry_run": true,
  "max_attempts": 1,
  "timeout_seconds": 180,
  "model_routes": {
    "generator": "ollama/gemma4:31b-cloud",
    "judge": "ollama/gpt-oss:120b-cloud",
    "verifier": "ollama/gpt-oss:120b-cloud"
  }
}
```

Fields:

- `seed_id`: required for the first slice. Only known fixture seed IDs are allowed.
- `run_id`: optional. If absent, generate a safe run ID like `fresh-demo-YYYYMMDD-HHMMSS`.
- `dry_run`: default `true`. Validates and returns a plan without model calls.
- `max_attempts`: default `1`, maximum `3`.
- `timeout_seconds`: default `180`, maximum `300`.
- `model_routes`: optional; defaults to the known asymmetric routes.

### Disabled Response

When fresh debate is not enabled:

```json
{
  "status": "attention_required",
  "run_id": null,
  "error": "fresh debate execution is disabled",
  "required_env": "BARRED_ENABLE_FRESH_DEBATE=true"
}
```

### Dry-Run Response

```json
{
  "status": "planned",
  "run_id": "fresh-demo-...",
  "dry_run": true,
  "seed_id": "fixture:first",
  "artifact_paths": {
    "run_dir": "/tmp/barred-fleet-runs/fresh-demo-...",
    "input_path": "/tmp/barred-fleet-runs/fresh-demo-.../training_corpus.jsonl",
    "attempts_path": "/tmp/barred-fleet-runs/fresh-demo-.../attempts.jsonl",
    "deterministic_eval_result_path": "/tmp/barred-fleet-runs/fresh-demo-.../deterministic_eval_result.json"
  },
  "limits": {
    "max_attempts": 1,
    "timeout_seconds": 180
  },
  "model_routes": {
    "generator": "ollama/gemma4:31b-cloud",
    "judge": "ollama/gpt-oss:120b-cloud",
    "verifier": "ollama/gpt-oss:120b-cloud"
  }
}
```

### Live Success Response

Live success should return the same report shape as `report_barred_run`, plus enough execution metadata to distinguish it from curated reporting:

```json
{
  "status": "ok",
  "run_id": "fresh-demo-...",
  "execution": {
    "fresh": true,
    "dry_run": false,
    "seed_id": "fixture:first",
    "artifact_scope": "tmp",
    "timeout_seconds": 180
  },
  "artifact_paths": {
    "input_path": "/tmp/barred-fleet-runs/fresh-demo-.../training_corpus.jsonl",
    "attempts_path": "/tmp/barred-fleet-runs/fresh-demo-.../attempts.jsonl",
    "deterministic_eval_result_path": "/tmp/barred-fleet-runs/fresh-demo-.../deterministic_eval_result.json"
  },
  "b_gate": {
    "status": "ok",
    "passed": true
  }
}
```

The exact B-gate metrics depend on the generated run and should not be hardcoded.

## Environment Flags

Fresh execution must be disabled by default:

```text
BARRED_ENABLE_FRESH_DEBATE=false
```

To allow dry-run planning without live model calls:

```text
BARRED_ENABLE_FRESH_DEBATE=true
BARRED_ENABLE_LIVE_FRESH_DEBATE=false
```

To allow live calls:

```text
BARRED_ENABLE_FRESH_DEBATE=true
BARRED_ENABLE_LIVE_FRESH_DEBATE=true
```

Recommended first deployment keeps live mode disabled. Enable live mode only for a controlled manual smoke.

## Code Style

Keep the module adapter-shaped and explicit:

```python
def plan_fresh_debate_run(request: FreshDebateRequest) -> FreshDebatePlan:
    seed = load_allowed_fixture_seed(request.seed_id)
    limits = validate_limits(request.max_attempts, request.timeout_seconds)
    run_id = normalize_or_create_run_id(request.run_id)
    return FreshDebatePlan(
        run_id=run_id,
        seed_id=seed.seed_id,
        artifact_paths=build_tmp_artifact_paths(run_id),
        limits=limits,
        model_routes=resolve_model_routes(request.model_routes),
    )
```

Rules:

- Validate before calling models.
- Keep fresh execution code separate from curated run reporting.
- Prefer dataclasses or Pydantic models for request/plan/response structure.
- Return structured `attention_required` responses for disabled or invalid execution modes.
- Do not bury live model calls inside import-time side effects.
- Do not mutate global demo registry state.

## Testing Strategy

### Unit Tests

Add `barred-fleet/tests/unit/test_fresh_debate.py`.

Required cases:

1. Disabled mode returns `attention_required` and names the required env flag.
2. Dry-run mode returns `planned` and writes no model artifacts.
3. Unknown `seed_id` is rejected.
4. `max_attempts > 3` is rejected.
5. `timeout_seconds > 300` is rejected.
6. Unsafe `run_id` characters are rejected or normalized.
7. Fake runner success writes temp artifacts and returns a report-compatible payload.
8. Fake runner failure returns `attention_required` or `error` without crashing FastAPI.

### Integration Tests

Use FastAPI `TestClient` with monkeypatched runner functions.

Required cases:

- `POST /runs/fresh-demo` dry-run returns `200`.
- disabled live mode does not call model runner.
- fake live runner returns report JSON.

### Manual Cloud Tests

Manual only, because live calls can cost money:

```bash
make verify-demo
```

Then, only after deploy approval:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "$(DEMO_URL)/runs/fresh-demo" \
  -d '{"seed_id":"fixture:first","dry_run":true,"max_attempts":1}'
```

Run live mode once only after budget approval.

## Boundaries

- Always: Preserve `report_barred_run(run_id=...)`.
- Always: Preserve `/demo/report?run_id=pilot-v1-calibrated-pecan`.
- Always: Preserve `make verify-demo`.
- Always: Require explicit env flags for fresh execution.
- Always: Keep live model calls disabled by default.
- Always: Bound live execution to one seed and a tiny attempt count in the first slice.
- Ask first: Enable live mode in deployed Cloud Run.
- Ask first: Run a live model smoke test.
- Ask first: Add new dependencies.
- Ask first: Add Firestore writes, GCS writes, queues, or Cloud Run Jobs.
- Ask first: Make any endpoint public.
- Never: Accept a 1.5GB corpus upload through HTTP.
- Never: Execute arbitrary user-provided shell commands or paths.
- Never: Store large code/corpus bodies in Firestore.
- Never: Claim production-scale fresh debate execution from this slice.

## Success Criteria

The first implementation is done when:

- `POST /runs/fresh-demo` exists.
- Disabled mode is safe and test-covered.
- Dry-run mode works locally without model calls.
- Fake-runner live mode is test-covered.
- A manual authenticated cloud dry-run returns `planned`.
- The curated demo still passes `make verify-demo`.
- Documentation clearly says temp artifacts are not production persistence.
- No Firestore write, GCS upload, async queue, Agent Gateway, Model Armor, or reflection feature is accidentally introduced in this slice.

## Deployment Evidence To Capture After Implementation

Implementation evidence captured after explicit deploy approval:

- Cloud Run revision: `barred-fleet-00025-zs6`.
- Deployed env: `BARRED_ENABLE_FRESH_DEBATE=true`.
- Deployed env: `BARRED_ENABLE_LIVE_FRESH_DEBATE=false`.
- `make verify-demo` passed after deploy.
- `make verify-fresh-demo` passed after deploy.
- Authenticated `POST /runs/fresh-demo` dry-run returned `status=planned`.
- Authenticated non-dry-run `POST /runs/fresh-demo` returned `status=attention_required` with `required_env=BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.
- No live model run was executed or claimed in this slice.

## Open Questions

1. Which exact existing debate entrypoint should be wrapped for the first fake-runner-to-real-runner transition?
2. Which fixture seed should be the canonical `fixture:first` seed?
3. Should the first live smoke use Ollama Cloud routes or Vertex/Gemini routes?
4. Should live fresh execution be exposed through the ADK agent as a tool immediately, or only through FastAPI until stable?
5. Should `/demo` display the latest fresh temp run, or should it remain fixed to the curated `pilot-v1-calibrated-pecan` proof until persistence exists?

## Recommended Implementation Order

1. Add request/plan models and dry-run planner in `app/fresh_debate.py`.
2. Add unit tests for disabled, dry-run, and validation behavior.
3. Add `POST /runs/fresh-demo` route.
4. Add fake-runner live path and tests.
5. Wire real debate runner behind `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.
6. Run local tests.
7. Deploy only after explicit approval.
8. Run `make verify-demo`.
9. Run authenticated cloud dry-run.
10. Decide whether one live smoke is worth the budget.

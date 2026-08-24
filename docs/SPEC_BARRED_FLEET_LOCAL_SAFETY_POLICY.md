# Spec: BARRED-Fleet Local Safety Policy

## Objective
Make the current local safety posture explicit, testable, and visible before adding external safety products such as Model Armor or Agent Gateway.
The service should reject unsupported run inputs deterministically, document what was enforced, and expose the active policy in `/runs`, `/runs/{run_id}/report`, `/seeds/manifest`, and the demo UI.

## Tech Stack
- Input policy in `barred-fleet/app/fresh_debate.py`.
- Product lifecycle/report aggregation in `barred-fleet/app/run_lifecycle.py`.
- Demo UI in `barred-fleet/app/demo.py`.
- FastAPI routes in `barred-fleet/app/fast_api_app.py`.
- Unit tests in `barred-fleet/tests/unit/`.

## Commands
- Focused lint: `cd barred-fleet && uv run ruff check app/fresh_debate.py app/run_lifecycle.py app/demo.py tests/unit/test_fresh_debate.py tests/unit/test_run_lifecycle.py tests/unit/test_demo.py`
- Focused tests: `cd barred-fleet && uv run pytest tests/unit/test_fresh_debate.py tests/unit/test_run_lifecycle.py tests/unit/test_demo.py -q`
- Unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Deployed verification after approval: `cd barred-fleet && make verify-demo`

## Project Structure
- `fresh_debate.py` owns seed/run/model/limit safety checks.
- `run_lifecycle.py` carries safety policy into persisted lifecycle reports.
- `demo.py` renders the policy without changing backend behavior.
- `docs/` holds this spec.

## Code Style
Use an additive `safety_policy` object. Do not replace existing fields.

```python
{
    "safety_policy": {
        "status": "enforced",
        "seed_allowlist": ["fixture:first", "cve500:N"],
        "arbitrary_seed_paths_allowed": False,
        "raw_seed_text_exposed": False,
        "max_attempts": {"min": 1, "max": 3, "live_default_max": 1},
    }
}
```

## Testing Strategy
- Unit-test the policy object shape.
- Unit-test route responses expose policy for dry-run and report paths.
- Unit-test manifest includes the same safety posture.
- Unit-test UI contains the safety policy panel and wording.
- No live model calls, no Cloud Run mutation, no GCS writes.

## Boundaries
- Always: keep run IDs regex-limited and seed IDs allowlisted.
- Always: keep live debate gated by env flags and max live attempts.
- Always: avoid raw seed topic/predicate in public manifests or receipts.
- Ask first: add Model Armor, Agent Gateway, new IAM roles, or new network egress controls.
- Never: accept arbitrary file paths, URLs, or model route roles from the UI.

## Success Criteria
- `/seeds/manifest` includes `safety_policy`.
- `/runs` dry-run response includes `safety_policy`.
- `/runs/{run_id}/report` includes `safety_policy`.
- Demo page renders the local safety posture.
- Focused and full unit tests pass.

## Open Questions
- Later slice can map this local policy to Model Armor/Agent Gateway controls after the local contract is stable.

# Spec: BARRED-Fleet UI Product Report Panel

## Objective
Make the Cloud demo surface display product-shaped run reports, not only raw
fresh debate lifecycle responses. After a seed preview or bounded live run, the
UI should call `GET /runs/{run_id}/report` and render artifact-backed facts when
available.

## Tech Stack
- Server-rendered demo HTML in `barred-fleet/app/demo.py`.
- Existing FastAPI endpoints:
  - `POST /runs/fresh-demo` for dry-run preview compatibility.
  - `POST /runs` for product-shaped live run lifecycle.
  - `GET /runs/{run_id}/report` for read-only product report aggregation.
- Existing unit tests in `barred-fleet/tests/unit/test_demo.py`.

## Commands
- Focused UI tests: `cd barred-fleet && uv run pytest tests/unit/test_demo.py -q`
- Unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Demo verification after deploy: `cd barred-fleet && make verify-demo`

## Project Structure
- `barred-fleet/app/demo.py` owns demo markup and client-side JavaScript.
- `barred-fleet/tests/unit/test_demo.py` guards the rendered HTML contract.
- `docs/` holds this implementation spec.

## Code Style
Keep the page dependency-free and local to the service. Use the existing
`rows()` table helper and text-first state rendering rather than adding a
frontend framework.

```javascript
const report = await loadProductRunReport(data.run_id);
renderLiveResult(report);
```

## Testing Strategy
- Assert the generated HTML references `/runs/{run_id}/report`.
- Assert the live flow loads a product report after dry-run and after queued
  live execution.
- Preserve existing `/demo/report` curated report rendering.
- No paid model call is triggered by UI tests.

## Boundaries
- Always: keep dry-run as the first step before live run.
- Always: show lifecycle status even when artifact enrichment is unavailable.
- Always: show B-gate/eval/artifact facts only when the report endpoint provides
  them.
- Ask first: deploy, enable live flags, or trigger paid live Gemini calls.
- Never: make the UI decide acceptance; it only renders deterministic report
  facts.

## Success Criteria
- The live result panel calls `GET /runs/{run_id}/report` for product runs.
- The panel renders accepted/rejected counts, verifier parse/pass rates, B-gate
  pass/fail, deterministic eval score, and promotion status when present.
- Planned/blocked runs continue to render useful status without artifact facts.
- Existing demo smoke and unit tests continue to pass.

## Open Questions
- A later slice can add a richer artifact-backed report card layout once we
  capture a fresh promoted run with real artifacts.

# Spec: BARRED-Fleet Async Run Lifecycle v1

## Objective

Extend the product-shaped `/runs` API so a caller can request an asynchronous BARRED fresh debate lifecycle without waiting for the full debate execution in the HTTP response.

The first slice uses FastAPI `BackgroundTasks` inside the existing Cloud Run service. It does not add Pub/Sub, Cloud Tasks, a separate worker service, or a new deployment target.

Success path:

```text
POST /runs { async_mode=true, dry_run=false }
  -> validate bounded seed
  -> write status=queued
  -> return run_id immediately
  -> background task writes running
  -> existing fresh debate executor runs
  -> background task writes completed|blocked|failed

GET /runs/{run_id}
  -> returns current Firestore/local lifecycle status
```

## Tech Stack

- Python `>=3.11`
- FastAPI `BackgroundTasks`
- Existing `FreshDebateRequest`
- Existing `run_fresh_debate_async`
- Existing Firestore/local lifecycle status helpers in `barred-fleet/app/run_lifecycle.py`

## Commands

```bash
cd barred-fleet
uv run ruff check app/fast_api_app.py app/fresh_debate.py app/run_lifecycle.py tests/unit/test_run_lifecycle.py
uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_fresh_debate.py tests/unit/test_demo.py -q
uv run pytest tests/unit -q
```

## Project Structure

```text
barred-fleet/app/fresh_debate.py        Adds async_mode request field
barred-fleet/app/run_lifecycle.py       Adds queued/background lifecycle helpers
barred-fleet/app/fast_api_app.py        Wires BackgroundTasks into POST /runs only
barred-fleet/tests/unit/test_run_lifecycle.py Adds async lifecycle route tests
```

## Code Style

Keep async mode as a wrapper over the existing synchronous lifecycle:

```python
if request.async_mode and not request.dry_run:
    return queue_product_run(request, background_tasks)
return await create_product_run(request)
```

No new queue abstraction until the in-service background path is proven.

## Testing Strategy

- Unit tests use fake runners and fake writers/readers where possible.
- Route test uses `TestClient` to verify `POST /runs` accepts `async_mode=true`.
- No test calls live Gemini, Ollama, GCS, or Firestore.
- Existing `/runs/fresh-demo` tests must remain unchanged.

## Boundaries

- Always:
  - Preserve `/runs/fresh-demo`.
  - Default `async_mode=false`.
  - Keep `dry_run=true` non-live and non-background.
  - Keep `max_attempts=1` demo posture unless caller explicitly changes it within existing limits.
  - Preserve deterministic B-gate as acceptance authority.

- Ask first:
  - Adding Pub/Sub, Cloud Tasks, Scheduler, or a new worker service.
  - Running paid live model calls.
  - Changing Cloud Run auth/IAM.

- Never:
  - Store large JSONL artifacts in Firestore.
  - Let model narration decide acceptance.
  - Make `make verify-demo` paid or live by default.

## Success Criteria

- `POST /runs` accepts `async_mode=true`.
- Async live request writes/returns `queued` before the runner result.
- Background path records `running -> completed|blocked|failed`.
- `GET /runs/{run_id}` can observe the final status after background work.
- Existing synchronous `/runs` behavior still passes.
- Full `barred-fleet` unit suite passes.

## Open Questions

1. Should a future production queue use Cloud Tasks or Pub/Sub?
2. Should the UI poll `GET /runs/{run_id}` by default after live execution?
3. Should blocked/failed fresh runs upload minimal diagnostic receipts to GCS?

# Spec: BARRED-Fleet Packaged Debate Runtime

## Objective

Enable the deployed `barred-fleet` Cloud Run service to run a tiny fresh BARRED debate without depending on manually started local services.

The first production-shaped path is intentionally narrow:

```text
POST /runs/fresh-demo
  -> validate one fixture seed
  -> optionally start internal localhost A2A debate services
  -> call the existing judge endpoint
  -> write temporary artifacts under /tmp
  -> return a fresh-run response
```

This is a bridge from the current curated run-reporting demo to true cloud debate execution. It is not the final async/GCS/Firestore lifecycle.

## Tech Stack

- Python `>=3.11`
- FastAPI in `barred-fleet/app/fast_api_app.py`
- Google ADK / A2A runtime already used by `barred-fleet`
- Existing debate stack:
  - `src/agentbeats/`
  - `scenarios/debate/adk_debate_judge.py`
  - `scenarios/debate/debater.py`
  - `scenarios/debate/adk_debate_verifier.py`
  - `scenarios/debate/barred_test.toml`

## Commands

Local unit checks:

```bash
cd barred-fleet
uv run pytest tests/unit/test_fresh_debate.py tests/unit/test_debate_stack.py -q
uv run --extra lint ruff check app/fresh_debate.py app/debate_stack.py tests/unit/test_fresh_debate.py tests/unit/test_debate_stack.py
make verify-packaged-stack
```

Cloud dry-run verifier:

```bash
cd barred-fleet
make verify-fresh-demo
```

Live cloud execution remains disabled unless explicitly deployed with:

```bash
BARRED_ENABLE_FRESH_DEBATE=true
BARRED_ENABLE_LIVE_FRESH_DEBATE=true
BARRED_START_INTERNAL_DEBATE_STACK=true
```

## Project Structure

```text
barred-fleet/app/fresh_debate.py
  Fresh run API validation and execution hook.

barred-fleet/app/debate_stack.py
  Small subprocess lifecycle manager for the packaged internal debate stack.

barred-fleet/tests/unit/test_debate_stack.py
  Stack command, env, timeout, and cleanup behavior tests.

barred-fleet/scripts/verify_packaged_stack.py
  No-model startup smoke that verifies packaged judge/pro/con/verifier services become reachable and then clean up.

barred-fleet/src/agentbeats/
  Packaged copy of the AgentBeats runtime required by the internal debate stack.

barred-fleet/scenarios/debate/
  Packaged minimal debate scenario, judge, verifier, debater, and fixture seed files.

docs/SPEC_BARRED_FLEET_PACKAGED_DEBATE_RUNTIME.md
  This spec.
```

## Code Style

Prefer a small explicit lifecycle object over implicit background processes:

```python
config = DebateStackConfig.from_env(
    os.environ,
    judge_url=plan.judge_url,
    model_routes=plan.model_routes,
)
with start_internal_debate_stack(config) as stack:
    result = await execute_debate_case(payload=payload, judge_url=stack.judge_url)
```

Conventions:

- Safe defaults: internal stack disabled unless explicitly enabled.
- Bounded execution: startup timeout and subprocess cleanup are mandatory.
- No shell interpolation for subprocess commands.
- Preserve existing `judge_url` behavior when the internal stack flag is off.

## Testing Strategy

Use unit tests with fake process factories and fake readiness probes. Do not start real model processes in unit tests.

Required tests:

1. Disabled internal stack returns the configured external judge URL unchanged.
2. Enabled internal stack builds the packaged `src/agentbeats/run_scenario.py scenarios/debate/barred_test.toml --serve-only` command.
3. Runtime env passes model routes into `JUDGE_MODEL`, `DEBATER_MODEL`, `GENERATOR_MODEL`, and `VERIFIER_MODEL`.
4. Startup timeout terminates spawned process and raises a clear error.
5. Context exit terminates the process.
6. `fresh_debate` uses the stack manager only when `BARRED_START_INTERNAL_DEBATE_STACK=true`.

## Boundaries

- Always: Preserve current `/demo`, `/demo/report`, and `report_barred_run` behavior.
- Always: Keep live fresh execution disabled by default.
- Always: Keep `make verify-fresh-demo` proving dry-run and safe refusal.
- Always: Clean up internal subprocesses on success, failure, or cancellation.
- Ask first: Deploy with `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.
- Ask first: Add heavy dependencies to `barred-fleet/pyproject.toml`.
- Ask first: Copy the full `src/agentbeats` and `scenarios/debate` runtime into the deploy source.
- Never: Accept arbitrary scenario paths from HTTP requests.
- Never: Run more than the bounded fixture seed in this slice.
- Never: Claim Firestore/GCS write lifecycle or async jobs from this slice.

## Success Criteria

- `app/debate_stack.py` exposes a test-covered stack lifecycle manager.
- `app/fresh_debate.py` can wrap the existing A2A call in that lifecycle manager.
- Internal stack startup remains opt-in through `BARRED_START_INTERNAL_DEBATE_STACK=true`.
- Existing unit tests pass.
- `make verify-packaged-stack` passes without live model inference.
- Fresh dry-run cloud verification still passes.
- Documentation states that deploy packaging of full debate source is the next deployment step, not already complete unless verified.

## Open Questions

1. Should the first live cloud smoke package the full root project inside `barred-fleet`, or should it deploy judge/pro/con/verifier as separate Cloud Run services?
2. Should the internal stack start once at app startup or per fresh run?
3. Should model routes remain Ollama Cloud for the first live run or switch to Vertex/Gemini Flash?

## Recommended First Slice

Implement only the stack lifecycle manager and the `fresh_debate` hook:

- no deploy packaging change yet;
- no live model call;
- no GCS/Firestore writes;
- no async queue.

This converts the current live runner from “assumes a local judge already exists” to “can start the packaged local debate stack when explicitly enabled.”

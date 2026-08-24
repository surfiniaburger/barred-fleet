# Spec: BARRED-Fleet Gemini Live Routing

## Objective

Enable one fresh cloud debate attempt to use Google-hosted Gemini models through Vertex/LiteLLM instead of Ollama localhost routing.

The immediate user is the hackathon demo/operator. Success means the Cloud Run runtime can start the packaged internal A2A stack and route pro/con/judge/verifier model calls to Gemini without trying `localhost:11434`.

## Tech Stack

- Cloud Run service: `barred-fleet`
- Runtime project: `gem-creation`
- Agent framework: Google ADK plus A2A SDK
- Completion adapter: LiteLLM Vertex provider
- Default live debate routes:
  - Pro debater: `vertex_ai/gemini-3.5-flash-lite`
  - Con debater: `vertex_ai/gemini-3.5-flash-lite`
  - Judge: `vertex_ai/gemini-3.6-flash`
  - Verifier: `vertex_ai/gemini-3.6-flash`

## Commands

```bash
cd barred-fleet
uv run pytest tests/unit/test_debate_stack.py tests/unit/test_fresh_debate.py tests/unit/test_agentbeats_replay.py -q
uv run --extra lint ruff check app/debate_stack.py app/fresh_debate.py src/agentbeats/replay.py tests/unit/test_debate_stack.py tests/unit/test_fresh_debate.py tests/unit/test_agentbeats_replay.py
make verify-packaged-stack
make verify-fresh-demo
```

Safe deploy:

```bash
agents-cli deploy --project gem-creation --region us-east1 --service-account barred-fleet-runtime@gem-creation.iam.gserviceaccount.com --min-instances 0 --max-instances 1 --concurrency 1 --no-confirm-project --update-env-vars BARRED_ENABLE_FRESH_DEBATE=true,BARRED_ENABLE_LIVE_FRESH_DEBATE=false,BARRED_START_INTERNAL_DEBATE_STACK=false,BARRED_DEBATE_RUNTIME_ROOT=/code,BARRED_DEBATE_STACK_STARTUP_TIMEOUT=60
```

One live retry, only after explicit approval:

```bash
gcloud run services update barred-fleet --project gem-creation --region us-east1 --update-env-vars BARRED_ENABLE_FRESH_DEBATE=true,BARRED_ENABLE_LIVE_FRESH_DEBATE=true,BARRED_START_INTERNAL_DEBATE_STACK=true,BARRED_DEBATE_RUNTIME_ROOT=/code,BARRED_DEBATE_STACK_STARTUP_TIMEOUT=60
```

## Project Structure

- `barred-fleet/app/fresh_debate.py` defines default live role routes.
- `barred-fleet/app/debate_stack.py` injects model route and Vertex environment variables into the packaged A2A stack subprocess.
- `barred-fleet/src/agentbeats/replay.py` normalizes provider kwargs before calling LiteLLM.
- `barred-fleet/tests/unit/` contains route and kwargs regressions.

## Code Style

Prefer explicit provider helpers over inline string checks:

```python
def is_gemini_model(model: str) -> bool:
    model_lower = model.lower()
    return "gemini" in model_lower and (
        model_lower.startswith("vertex_ai/") or model_lower.startswith("gemini/")
    )
```

Keep behavior backward-compatible for existing Ollama/local routes.

## Testing Strategy

- Unit tests verify Gemini defaults and Vertex environment injection.
- Unit tests verify Ollama-only options such as `keep_alive` are stripped for Gemini/Vertex.
- Unit tests verify deprecated Gemini 3.x sampling params are not sent to LiteLLM.
- Existing packaged-stack smoke remains no-model and only verifies A2A startup/cleanup.

## Boundaries

- Always: keep `BARRED_ENABLE_LIVE_FRESH_DEBATE=false` after smoke attempts.
- Always: keep Ollama/local routes working for local flows.
- Always: record failures truthfully; do not claim successful fresh debate unless a run completes.
- Ask first: any additional paid live retry after one bounded attempt.
- Never: deploy public unauthenticated live execution.
- Never: add Model Garden endpoints for this slice.

## Success Criteria

- Default fresh debate routes no longer contain `ollama/`.
- Cloud Run stack subprocess receives `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION`.
- Gemini 3.x calls do not receive `temperature`, `top_p`, `top_k`, or Ollama `options.keep_alive`.
- `make verify-fresh-demo` passes after safe deploy.
- One explicitly approved live attempt no longer fails with `localhost:11434`.
- `fresh-gemini-live-20260818-212644` completed Cloud Run fresh orchestration through the packaged internal A2A stack; it did not produce an accepted sample because consensus failed with `max_refinements=0`.

## Open Questions

- Whether `VERTEXAI_LOCATION=global` is accepted for all selected Gemini routes in the current project; if not, use `us-central1` or `us-east1` for the live smoke.

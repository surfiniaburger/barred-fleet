# Spec: BARRED-Fleet Agent Gateway Local Adapter

## Objective
Add a product-shaped Agent Gateway boundary to BARRED-Fleet before any real cloud gateway integration. The gateway protects model/tool egress policy, route allowlists, identity metadata, and bounded run limits. It does **not** decide whether generated vulnerability evidence is accepted; deterministic B-gate remains the acceptance authority.

## Tech Stack
- Python 3.11 BARRED-Fleet FastAPI/ADK runtime.
- Existing `FreshDebateRequest`, `FreshDebatePlan`, and product run lifecycle.
- No new external dependencies in this slice.
- Cloud integration remains future work; this slice uses a local adapter only.

## Commands
- Focused lint/tests: `cd barred-fleet && uv run ruff check app/agent_gateway.py app/fresh_debate.py app/run_lifecycle.py tests/unit/test_agent_gateway.py tests/unit/test_fresh_debate.py tests/unit/test_run_lifecycle.py && uv run pytest tests/unit/test_agent_gateway.py tests/unit/test_fresh_debate.py tests/unit/test_run_lifecycle.py -q`
- Full unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Remote smoke after deploy: `cd barred-fleet && make verify-fresh-demo`

## Project Structure
- `barred-fleet/app/agent_gateway.py` -> gateway policy adapter and receipts.
- `barred-fleet/app/fresh_debate.py` -> call gateway before live execution.
- `barred-fleet/app/run_lifecycle.py` -> persist/report gateway receipts.
- `barred-fleet/tests/unit/test_agent_gateway.py` -> adapter behavior.
- `barred-fleet/tests/unit/test_fresh_debate.py` and `test_run_lifecycle.py` -> integration contract.

## Code Style
Use small receipt-building functions and avoid leaking raw seed/prompt text.

```python
receipt = gateway.evaluate(plan)
if receipt["egress_decision"]["blocked"]:
    return _blocked_by_agent_gateway_response(plan, receipt)
```

Receipts must be JSON-serializable, explicit, and compatible with existing report rendering.

## Testing Strategy
- Unit-test `not_configured`, local pass, and local blocked modes.
- Fresh-debate tests prove blocked egress does not reach the runner.
- Product lifecycle tests prove `agent_gateway` receipts are persisted and returned by `/runs/{run_id}/report`.
- Remote smoke should remain non-paid: live flags can stay off; gateway pass/block receipts must occur before live refusal or runner invocation.

## Boundaries
- Always:
  - Keep B-gate as vulnerability acceptance authority.
  - Screen before live runner/model calls.
  - Preserve `max_attempts <= 1` demo default.
  - Do not store raw seed text in gateway receipts.
- Ask first:
  - Real Google Agent Gateway/API integration.
  - New IAM roles, service accounts, or network egress changes.
  - New dependencies.
- Never:
  - Treat gateway pass as vulnerability acceptance.
  - Allow arbitrary model routes or tool names through the adapter.
  - Trigger paid live debate from a smoke test.

## Success Criteria
- Reports expose `agent_gateway.status` as `not_configured | configured | blocked | error`.
- Reports expose `decision_authority: routing_and_egress_only` when configured.
- Reports include `tool_egress_policy`, `model_route_policy`, and `egress_decision`.
- Local gateway mode can block an unsafe route/tool request before live execution.
- Normal configured route passes gateway and still refuses safely when live flags are off.
- Tests and `make verify-fresh-demo` pass without triggering a live Gemini debate.

## Open Questions
- Which real Google Agent Gateway product/API should back the future cloud mode?
- Whether gateway policy should eventually enforce per-user quotas or remain service-level only.

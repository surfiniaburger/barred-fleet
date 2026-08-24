# Spec: BARRED-Fleet Agent Gateway Cloud Integration V1

## Objective
Integrate BARRED-Fleet with real Google Agent Gateway governance without changing the product/report contract already proven by the local adapter.

Agent Gateway protects model/tool egress, route policy, identity, and observability for agent interactions. It does **not** decide vulnerability acceptance. BARRED deterministic B-gate remains the sole acceptance authority for generated vulnerability evidence.

This V1 is intentionally conservative: keep the local adapter as the stable application boundary, add cloud discovery/configuration behind it, and fail closed before live debate execution if the configured cloud gateway is unavailable or denies egress.

## Current Baseline
- Cloud Run service: `barred-fleet`.
- Live fresh debate defaults remain closed:
  - `BARRED_ENABLE_LIVE_FRESH_DEBATE=false`
  - `BARRED_START_INTERNAL_DEBATE_STACK=false`
  - `BARRED_MAX_LIVE_FRESH_ATTEMPTS=1`
- Model Armor is already configured for seed screening:
  - `BARRED_MODEL_ARMOR_MODE=cloud_model_armor`
  - `BARRED_MODEL_ARMOR_TEMPLATE_ID=barred-seed-screen-v1`
- Local Agent Gateway adapter is deployed:
  - `BARRED_AGENT_GATEWAY_MODE=local_policy`
  - reports expose `agent_gateway.status`, `decision_authority`, `model_route_policy`, `tool_egress_policy`, and `egress_decision`.
- `make verify-fresh-demo` proves:
  - normal configured route passes gateway and still refuses safely while live is off;
  - unsafe model route blocks before live execution;
  - Model Armor block path still blocks before live execution.

## Source Grounding
Google's current Agent Gateway documentation frames Agent Gateway as the Gemini Enterprise Agent Platform networking component that governs connectivity across users, agents, tools, and agent-to-agent interactions. It describes two modes: Client-to-Agent ingress and Agent-to-Anywhere egress. For BARRED-Fleet V1, the relevant path is Agent-to-Anywhere egress because fresh debate can call model/tool routes from a Cloud Run-hosted ADK runtime.

The same documentation says Agent Gateway integrates with Agent Registry, agent identity, Agent Platform policies, Model Armor, and observability, and supports HTTP-based traffic including MCP and A2A. It also notes registered tools/agents and IAM-backed authorization are central to enforcement.

References:
- Google Cloud Agent Gateway overview: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview`
- Google codelab for governing agentic workloads: `https://codelabs.developers.google.com/cloudnet-agent-gateway`

## Tech Stack
- Python 3.11 BARRED-Fleet FastAPI/ADK runtime.
- Cloud Run private service.
- Google ADK root agent.
- Google Cloud Model Armor for content safety.
- Google Agent Gateway / Agent Platform governance for route/tool egress.
- Firestore run registry and GCS artifacts remain unchanged.

## Environment Contract

Existing local mode:

```text
BARRED_AGENT_GATEWAY_MODE=not_configured|local_policy
BARRED_AGENT_GATEWAY_ALLOWED_MODEL_ROUTES=<pipe-or-comma-delimited routes>
BARRED_AGENT_GATEWAY_BLOCKED_MODEL_ROUTES=<pipe-or-comma-delimited routes>
BARRED_AGENT_GATEWAY_ALLOWED_TOOLS=<pipe-or-comma-delimited tools>
BARRED_AGENT_GATEWAY_BLOCKED_TOOLS=<pipe-or-comma-delimited tools>
```

Proposed cloud mode:

```text
BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway
BARRED_AGENT_GATEWAY_PROJECT=<project-id>
BARRED_AGENT_GATEWAY_LOCATION=<region>
BARRED_AGENT_GATEWAY_ID=<gateway-id-or-resource-name>
BARRED_AGENT_GATEWAY_POLICY_ID=<policy-id-or-resource-name>
BARRED_AGENT_GATEWAY_AUDIT_ONLY=false
```

Fallbacks:
- `BARRED_AGENT_GATEWAY_PROJECT` may fall back to `GOOGLE_CLOUD_PROJECT`.
- `BARRED_AGENT_GATEWAY_LOCATION` may fall back to `GOOGLE_CLOUD_LOCATION`.
- `BARRED_AGENT_GATEWAY_ID` and policy identity have no fallback; missing values block live execution fail-closed.

## Report Contract
Cloud mode must preserve the existing report shape.

Pass:

```json
{
  "agent_gateway": {
    "status": "configured",
    "control": "agent_gateway",
    "mode": "cloud_agent_gateway",
    "decision_authority": "routing_and_egress_only",
    "model_route_policy": {
      "checked": true,
      "blocked": false,
      "requested_routes": {
        "generator": "vertex_ai/gemini-3.5-flash-lite",
        "judge": "vertex_ai/gemini-3.6-flash"
      },
      "policy_name": "projects/.../locations/.../agentGateways/..."
    },
    "tool_egress_policy": {
      "checked": true,
      "blocked": false,
      "requested_tools": ["fresh_debate"]
    },
    "egress_decision": {
      "checked": true,
      "blocked": false,
      "context": "fresh_debate.live_execution",
      "reason": "passed"
    }
  }
}
```

Block:

```json
{
  "status": "blocked",
  "error_category": "egress_policy",
  "agent_gateway": {
    "status": "blocked",
    "decision_authority": "routing_and_egress_only",
    "egress_decision": {
      "checked": true,
      "blocked": true,
      "reason": "model_route_blocked"
    }
  },
  "b_gate": {
    "available": false,
    "passed": null
  }
}
```

Error / misconfiguration:

```json
{
  "status": "blocked",
  "error_category": "egress_policy",
  "agent_gateway": {
    "status": "error",
    "decision_authority": "routing_and_egress_only",
    "egress_decision": {
      "checked": true,
      "blocked": true,
      "reason": "cloud_agent_gateway_unavailable"
    }
  }
}
```

## Commands

Terraform provisioning scaffold:

```bash
cd barred-fleet/infra/agent-gateway
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
terraform output cloud_run_env_vars
```

The Terraform slice creates:

- `google_network_services_agent_gateway.barred`
- Google-managed `AGENT_TO_ANYWHERE` governed access path
- optional `roles/networkservices.viewer` grant for the BARRED-Fleet runtime service account

The default `enable_project_services=false` avoids surprising API enablement.
Set it to `true` only if this Terraform workspace should own `networkservices.googleapis.com`.

Non-paid Cloud Run verification must happen before any live model call:

```bash
gcloud run services update barred-fleet \
  --project gem-creation \
  --region us-east1 \
  --update-env-vars BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway,BARRED_AGENT_GATEWAY_PROJECT=gem-creation,BARRED_AGENT_GATEWAY_LOCATION=us-east1,BARRED_AGENT_GATEWAY_ID=barred-agent-gateway-v1,BARRED_AGENT_GATEWAY_POLICY_ID=projects/gem-creation/locations/us-east1/agentGateways/barred-agent-gateway-v1,BARRED_AGENT_GATEWAY_AUDIT_ONLY=false,BARRED_ENABLE_LIVE_FRESH_DEBATE=false,BARRED_START_INTERNAL_DEBATE_STACK=false,BARRED_MAX_LIVE_FRESH_ATTEMPTS=1 \
  --quiet
```

Then call `/runs/fresh-demo` with `dry_run=false` while live remains off.
Expected result is `status=attention_required`, live refusal, and
`agent_gateway.mode=cloud_agent_gateway` with `egress_decision.blocked=false`.
If the receipt reports `cloud_agent_gateway_unavailable` or
`missing_agent_gateway_configuration`, the gateway is not ready and paid live
debate must not be run.

Local validation:

```bash
cd barred-fleet
uv run ruff check app/agent_gateway.py app/fresh_debate.py app/run_lifecycle.py tests/unit/test_agent_gateway.py tests/unit/test_fresh_debate.py tests/unit/test_run_lifecycle.py
uv run pytest tests/unit/test_agent_gateway.py tests/unit/test_fresh_debate.py tests/unit/test_run_lifecycle.py -q
uv run pytest tests/unit -q
```

Current deployed safety smoke:

```bash
cd barred-fleet
make verify-fresh-demo
```

Cloud CLI discovery gate:

```bash
gcloud components update
gcloud network-services agent-gateways --help
gcloud help -- agent gateway
```

Current local finding: the installed `gcloud` does not expose `gcloud network-services agent-gateways` yet, and `gcloud help -- agent gateway` fails because the local gcloud installation cannot load a `grpc` module. Therefore V1 implementation must not assume local CLI syntax until the CLI is updated/repaired or REST/Terraform syntax is separately validated.

## Project Structure
- `barred-fleet/app/agent_gateway.py` -> extend adapter with `cloud_agent_gateway` mode.
- `barred-fleet/app/fresh_debate.py` -> no interface churn; continue calling `evaluate_egress(...)`.
- `barred-fleet/app/run_lifecycle.py` -> no schema churn; continue persisting `agent_gateway`.
- `barred-fleet/tests/unit/test_agent_gateway.py` -> cloud mode error/pass/block adapter tests with fake client.
- `barred-fleet/tests/unit/test_fresh_debate.py` -> cloud gateway block-before-runner tests.
- `barred-fleet/Makefile` -> optional non-paid cloud-gateway smoke once real gateway is configured.
- `docs/SPEC_BARRED_FLEET_AGENT_GATEWAY_CLOUD_INTEGRATION_V1.md` -> this spec.

## Code Style
Keep the cloud provider behind a small client boundary.

```python
class CloudAgentGatewayClient(Protocol):
    def evaluate_egress(
        self,
        *,
        gateway_resource: str,
        model_routes: Mapping[str, str],
        tool_names: Sequence[str],
        context: str,
    ) -> dict[str, Any]: ...
```

The application should convert provider responses into the stable BARRED receipt:

```python
receipt = gateway.evaluate_egress(
    model_routes=plan.model_routes,
    tool_names=["fresh_debate"],
    context="fresh_debate.live_execution",
)
if receipt["egress_decision"]["blocked"]:
    return _blocked_by_agent_gateway_response(plan, model_armor, receipt)
```

Do not leak raw seed text, prompt text, provider SDK objects, or provider exception types into the public run/report schema.

## Testing Strategy
- Unit tests first:
  - missing cloud gateway config returns `status=error` and blocks;
  - fake cloud client pass returns `status=configured`;
  - fake cloud client block returns `status=blocked`;
  - provider exception returns `status=error` and blocks;
  - `run_fresh_debate` does not call runner when gateway blocks.
- Integration smoke without model spend:
  - deploy with live flags off;
  - set `BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway`;
  - first smoke should be intentionally misconfigured or guaranteed-blocked;
  - assert no Gemini call occurs because block happens before live debate.
- Paid/live smoke only after non-paid pass/block evidence exists:
  - one allowed seed;
  - `max_attempts=1`;
  - Model Armor pass;
  - Agent Gateway pass;
  - GCS/Firestore/diagnostic receipt observed.

## Boundaries
- Always:
  - Keep deterministic B-gate as vulnerability acceptance authority.
  - Keep live fresh debate off by default.
  - Enforce `max_attempts <= 1` for demo cloud runs.
  - Preserve current `/runs`, `/runs/{run_id}`, `/runs/{run_id}/report`, and `/demo` schema.
  - Fail closed before live execution on gateway misconfiguration or denial.
  - Keep raw seed/prompt text out of receipts and Firestore.
- Ask first:
  - Creating real Agent Registry entries.
  - Creating real Agent Gateway resources.
  - Granting IAM roles beyond current Cloud Run runtime requirements.
  - Switching from Cloud Run ADK service to Agent Runtime.
  - Enabling live paid smoke.
- Never:
  - Treat Agent Gateway pass as acceptance of vulnerability evidence.
  - Use gateway policy to bypass B-gate.
  - Add arbitrary outbound tool/model routes for demo convenience.
  - Trigger live model calls in gateway smoke tests.

## Success Criteria
- Cloud mode is selectable with `BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway`.
- Missing/misconfigured cloud gateway blocks with `error_category=egress_policy`.
- Fake cloud pass/block tests preserve the same report contract as local mode.
- Normal local mode remains unchanged and `make verify-fresh-demo` still passes.
- Real cloud integration is not attempted until CLI/API commands and IAM are validated.
- Documentation clearly states Agent Gateway is routing/egress governance only, not acceptance authority.

## Implementation Plan

### Task 1 — Cloud Client Boundary
Add a `CloudAgentGatewayClient` protocol and `CloudAgentGateway` adapter class.

Acceptance:
- fake client pass/block/error can be tested without Google Cloud;
- no new runtime behavior unless `BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway`.

### Task 2 — Fail-Closed Config Loader
Resolve project/location/gateway/policy envs and return a blocking error receipt when required values are missing.

Acceptance:
- missing gateway ID blocks before live execution;
- report shows `agent_gateway.status=error`;
- `error_category=egress_policy`.

### Task 3 — Provider Response Normalizer
Normalize provider pass/block/error into the existing BARRED receipt schema.

Acceptance:
- `status` is one of `configured | blocked | error`;
- `decision_authority=routing_and_egress_only`;
- no provider-specific object leaks.

### Task 4 — Non-Paid Cloud Smoke
After CLI/API/IAM validation, deploy with cloud mode and live flags off.

Acceptance:
- misconfigured or guaranteed-blocked smoke returns before live debate;
- no Gemini debate call is made;
- `/runs/{run_id}/report` shows the cloud gateway receipt.

### Task 5 — Optional One-Seed Live Smoke
Only after Task 4 passes and with explicit approval.

Acceptance:
- one allowed seed;
- `max_attempts=1`;
- Model Armor pass;
- Agent Gateway pass;
- run status, GCS artifacts, Firestore metadata, deterministic receipt visible.

## Open Questions
- Is BARRED-Fleet staying on Cloud Run, or should the real Agent Gateway integration require migrating fresh debate to Google Agent Runtime?
- Which exact Google resource should represent the BARRED root agent and internal tools in Agent Registry?
- Is gateway policy enforcement required for Vertex/Gemini model routes, A2A judge calls, or both?
- Which IAM role set is minimal for runtime service identity and for setup/admin identity?

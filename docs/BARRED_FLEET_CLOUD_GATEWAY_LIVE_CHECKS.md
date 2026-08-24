# BARRED-Fleet Cloud Agent Gateway Live Check Runbook

## Objective

Run one bounded live `POST /runs` product-lifecycle check with real Google Agent Gateway verification enabled, then return Cloud Run to the closed/default posture.

This runbook is intentionally opt-in because the live run may call paid Gemini routes.

## Preconditions

- Cloud Run service exists: `barred-fleet`.
- Project: `gem-creation`.
- Region: `us-east1`.
- Runtime service account: `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
- Agent Gateway exists:
  - `projects/gem-creation/locations/us-east1/agentGateways/barred-agent-gateway-v1`
- Model Armor template exists:
  - `projects/gem-creation/locations/us-east1/templates/barred-seed-screen-v1`
- Baseline closed checks pass:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
make verify-demo
make verify-fresh-demo
```

## Step 1: Configure Cloud Gateway Mode With Live Still Off

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet

SERVICE_URL="https://barred-fleet-837262597425.us-east1.run.app"

gcloud run services update barred-fleet \
  --project gem-creation \
  --region us-east1 \
  --update-env-vars BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway,BARRED_AGENT_GATEWAY_PROJECT=gem-creation,BARRED_AGENT_GATEWAY_LOCATION=us-east1,BARRED_AGENT_GATEWAY_ID=barred-agent-gateway-v1,BARRED_AGENT_GATEWAY_POLICY_ID=projects/gem-creation/locations/us-east1/agentGateways/barred-agent-gateway-v1,BARRED_AGENT_GATEWAY_AUDIT_ONLY=false,BARRED_ENABLE_LIVE_FRESH_DEBATE=false,BARRED_START_INTERNAL_DEBATE_STACK=false,BARRED_MAX_LIVE_FRESH_ATTEMPTS=1 \
  --quiet
```

## Step 2: Non-Paid Refusal Smoke

This verifies Cloud Agent Gateway and Model Armor while live execution remains disabled.

```bash
token="$(gcloud auth print-identity-token)"

curl -sS -X POST \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  "$SERVICE_URL/runs/fresh-demo" \
  -d '{"seed_id":"fixture:first","run_id":"cloud-gateway-refusal-smoke","dry_run":false,"max_attempts":1}' \
  | tee /tmp/cloud-gateway-refusal-smoke.json \
  | python3 -m json.tool
```

Expected minimum fields:

```json
{
  "status": "attention_required",
  "error": "live fresh debate execution is disabled",
  "model_armor": {
    "status": "configured"
  },
  "agent_gateway": {
    "status": "configured",
    "mode": "cloud_agent_gateway",
    "cloud_control_plane": {
      "checked": true,
      "blocked": false
    },
    "egress_decision": {
      "blocked": false,
      "reason": "passed"
    }
  }
}
```

Do not proceed to a paid live run if `agent_gateway.status` is `error`, if `egress_decision.blocked` is `true`, or if the response contains `cloud_agent_gateway_unavailable`.

## Step 3: Enable Bounded Live Product Run

```bash
gcloud run services update barred-fleet \
  --project gem-creation \
  --region us-east1 \
  --update-env-vars BARRED_ENABLE_FRESH_DEBATE=true,BARRED_ENABLE_LIVE_FRESH_DEBATE=true,BARRED_START_INTERNAL_DEBATE_STACK=true,BARRED_MAX_LIVE_FRESH_ATTEMPTS=1 \
  --quiet
```

## Step 4: Start One Product Lifecycle Run

```bash
token="$(gcloud auth print-identity-token)"
run_id="product-cloud-gateway-live-$(date +%Y%m%d-%H%M%S)"

curl -sS -X POST \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  "$SERVICE_URL/runs" \
  -d "{\"seed_id\":\"fixture:first\",\"run_id\":\"$run_id\",\"dry_run\":false,\"async_mode\":true,\"max_attempts\":1}" \
  | tee "/tmp/$run_id-create.json" \
  | python3 -m json.tool

echo "$run_id"
```

## Step 5: Poll Product Run Status

```bash
for i in {1..30}; do
  token="$(gcloud auth print-identity-token)"
  curl -sS \
    -H "Authorization: Bearer $token" \
    "$SERVICE_URL/runs/$run_id" \
    | tee "/tmp/$run_id-status.json" \
    | python3 -m json.tool

  status="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get("status", ""))' "/tmp/$run_id-status.json")"
  [[ "$status" == "completed" || "$status" == "blocked" || "$status" == "failed" ]] && break
  sleep 5
done
```

## Step 6: Fetch Artifact-Backed Product Report

```bash
token="$(gcloud auth print-identity-token)"

curl -sS \
  -H "Authorization: Bearer $token" \
  "$SERVICE_URL/runs/$run_id/report" \
  | tee "/tmp/$run_id-report.json" \
  | python3 -m json.tool
```

## Step 7: Check Required Proof Fields

```bash
python3 - <<PY
import json
p = json.load(open(f"/tmp/{'$'}run_id-report.json"))
print("status:", p.get("lifecycle", {}).get("status") or p.get("status"))
print("run_id:", p.get("run_id"))
print("seed_id:", p.get("seed_id"))
print("model_armor:", p.get("model_armor", {}).get("status"), p.get("model_armor", {}).get("mode"))
print("agent_gateway:", p.get("agent_gateway", {}).get("status"), p.get("agent_gateway", {}).get("mode"))
print("gateway_blocked:", p.get("agent_gateway", {}).get("egress_decision", {}).get("blocked"))
print("b_gate:", p.get("b_gate", {}).get("passed"))
print("promotion:", p.get("promotion", {}).get("status"), p.get("promotion", {}).get("reason"))
print("deterministic_eval:", p.get("deterministic_eval", {}).get("score"))
PY
```

Green proof requires:

- lifecycle `status=completed`
- `model_armor.status=configured`
- `model_armor.mode=cloud_model_armor`
- `agent_gateway.status=configured`
- `agent_gateway.mode=cloud_agent_gateway`
- `agent_gateway.egress_decision.blocked=false`
- `b_gate.passed=true`
- `promotion.status=promoted`
- `promotion.reason=gcs_and_firestore_written`
- `deterministic_eval.score=1.0`

A completed run with `b_gate.passed=false` still proves live execution works, but it does not prove accepted artifact promotion.

## Step 8: Return To Closed Posture

Always run this after the live check, even if the live run fails.

```bash
gcloud run services update barred-fleet \
  --project gem-creation \
  --region us-east1 \
  --update-env-vars BARRED_ENABLE_LIVE_FRESH_DEBATE=false,BARRED_START_INTERNAL_DEBATE_STACK=false,BARRED_MAX_LIVE_FRESH_ATTEMPTS=1 \
  --quiet
```

Then confirm refusal/block contracts still pass:

```bash
make verify-fresh-demo
```

## Notes

- The live run is intentionally bounded to `max_attempts=1`.
- The seed selector must remain allowlisted: `fixture:first` or `cve500:N`.
- Firestore stores metadata only. GCS stores artifacts.
- Agent Gateway governs route/tool egress only. Deterministic B-gate remains the acceptance authority.

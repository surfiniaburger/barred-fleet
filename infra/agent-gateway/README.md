# BARRED-Fleet Agent Gateway V1

This Terraform slice provisions the minimum Google Network Services `AgentGateway`
resource needed for BARRED-Fleet to verify a real Google Agent Gateway control
plane before live debate execution.

The BARRED application still keeps deterministic B-gate as the vulnerability
acceptance authority. Agent Gateway only governs route/tool egress.

## What This Proves

- A real Google-managed Agent Gateway resource exists in `us-east1`.
- The BARRED-Fleet Cloud Run runtime service account can read/verify it.
- `BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway` can fail closed before live
  execution if the gateway is missing, unreachable, or not `AGENT_TO_ANYWHERE`.

This V1 does **not** claim transparent Cloud Run traffic interception. The app
still enforces its own route/tool policy after verifying the cloud control-plane
resource.

## Files

- `versions.tf` pins Terraform and Google provider requirements.
- `main.tf` creates `google_network_services_agent_gateway.barred`.
- `variables.tf` defines project, region, gateway ID, and IAM toggles.
- `outputs.tf` prints the Cloud Run env vars needed by BARRED-Fleet.
- `terraform.tfvars.example` is the copyable starting point.

## Setup

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet/infra/agent-gateway
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
```

If `networkservices.googleapis.com` is not already enabled and this workspace
should own API enablement, set this in `terraform.tfvars`:

```hcl
enable_project_services = true
```

Apply only after reviewing the plan:

```bash
terraform apply
```

## Deploy BARRED-Fleet In Cloud Gateway Verification Mode

After apply, inspect outputs:

```bash
terraform output agent_gateway_id
terraform output cloud_run_env_vars
```

Then update Cloud Run with live still off:

```bash
gcloud run services update barred-fleet \
  --project gem-creation \
  --region us-east1 \
  --update-env-vars BARRED_AGENT_GATEWAY_MODE=cloud_agent_gateway,BARRED_AGENT_GATEWAY_PROJECT=gem-creation,BARRED_AGENT_GATEWAY_LOCATION=us-east1,BARRED_AGENT_GATEWAY_ID=barred-agent-gateway-v1,BARRED_AGENT_GATEWAY_POLICY_ID=projects/gem-creation/locations/us-east1/agentGateways/barred-agent-gateway-v1,BARRED_AGENT_GATEWAY_AUDIT_ONLY=false,BARRED_ENABLE_LIVE_FRESH_DEBATE=false,BARRED_START_INTERNAL_DEBATE_STACK=false,BARRED_MAX_LIVE_FRESH_ATTEMPTS=1 \
  --quiet
```

## Non-Paid Smoke

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
SERVICE_URL="https://barred-fleet-837262597425.us-east1.run.app"
token="$(gcloud auth print-identity-token)"

curl -sS -X POST \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  "$SERVICE_URL/runs/fresh-demo" \
  -d '{"seed_id":"fixture:first","run_id":"cloud-gateway-refusal-smoke","dry_run":false,"max_attempts":1}' \
  | python3 -m json.tool
```

Expected receipt:

```json
{
  "status": "attention_required",
  "error": "live fresh debate execution is disabled",
  "agent_gateway": {
    "status": "configured",
    "mode": "cloud_agent_gateway",
    "egress_decision": {
      "blocked": false
    }
  }
}
```

If the receipt says `cloud_agent_gateway_unavailable` or
`missing_agent_gateway_configuration`, do not run a paid live debate yet.

.PHONY: test-tools test-unit demo-smoke product-report-smoke verify-product-run gepa-memory-preview-local gepa-memory-preview-smoke verify-gepa-memory-preview verify-demo verify-fresh-demo verify-packaged-stack eval-artifact-gate-generate eval-artifact-gate-grade eval-artifact-gate-grade-deterministic eval-report-generate eval-report-grade-deterministic

ADK_EVAL_URL ?= http://127.0.0.1:18100
ADK_APP_NAME ?= app
ADK_EVAL_CONCURRENCY ?= 1
DEMO_URL ?= https://barred-fleet-837262597425.us-east1.run.app
DEMO_PROMPT ?= Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.
DEMO_RUN_ID ?= pilot-v1-calibrated-pecan

test-tools:
	uv run pytest tests/unit/test_tools.py -q

test-unit:
	uv run pytest tests/unit -q

demo-smoke:
	agents-cli run --url $(DEMO_URL) --mode adk "$(DEMO_PROMPT)"

verify-product-run: product-report-smoke

product-report-smoke:
	@echo "[product-report-smoke] checking authenticated dry-run /runs report contract"
	@run_id="product-report-smoke-$$(date +%Y%m%d%H%M%S)"; \
	token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-product-create.json -w '%{http_code}' -X POST -H "Authorization: Bearer $$token" -H "Content-Type: application/json" "$(DEMO_URL)/runs" -d "{\"seed_id\":\"fixture:first\",\"run_id\":\"$$run_id\",\"dry_run\":true,\"max_attempts\":1}")"; \
	if [ "$$status" != "200" ]; then \
		echo "[product-report-smoke] expected POST /runs HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	status="$$(curl -sS -o /tmp/barred-fleet-product-report.json -w '%{http_code}' -H "Authorization: Bearer $$token" "$(DEMO_URL)/runs/$$run_id/report")"; \
	if [ "$$status" != "200" ]; then \
		echo "[product-report-smoke] expected GET /runs/$$run_id/report HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; create = json.load(open(sys.argv[1])); report = json.load(open(sys.argv[2])); assert create["status"] == "planned"; assert report["status"] == "ok"; assert report["run_id"] == create["run_id"]; assert report["lifecycle"]["status"] == "planned"; assert report["seed_metadata"]["seed_id"] == "fixture:first"; assert report["artifact_report"]["available"] is False; assert report["artifact_report"]["reason"] == "planned_run_has_no_final_artifacts"; assert report["b_gate"]["available"] is False; assert report["b_gate"]["passed"] is None; assert report["b_gate"]["invariant_scorecard"]["available"] is False; print("[product-report-smoke] /runs report contract passed:", report["run_id"])' /tmp/barred-fleet-product-create.json /tmp/barred-fleet-product-report.json

gepa-memory-preview-local:
	@echo "[gepa-memory-preview-local] checking local GEPA memory preview"
	@uv run python -c 'from app.gepa_memory import build_gepa_memory_preview; payload = build_gepa_memory_preview(); assert payload["status"] in {"ok", "attention_required"}; assert payload["source"] == "local"; assert payload["write_enabled"] is False; assert "memory" in payload; print("[gepa-memory-preview-local] local preview contract passed:", payload["status"])'

gepa-memory-preview-smoke:
	@echo "[gepa-memory-preview-smoke] checking authenticated /memory/gepa/preview contract"
	@token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-gepa-memory-preview.json -w '%{http_code}' -H "Authorization: Bearer $$token" "$(DEMO_URL)/memory/gepa/preview")"; \
	if [ "$$status" != "200" ]; then \
		echo "[gepa-memory-preview-smoke] expected authenticated /memory/gepa/preview HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; payload = json.load(open(sys.argv[1])); assert payload["status"] in {"ok", "attention_required"}; assert payload["source"] in {"local", "gcs"}; assert payload["write_enabled"] is False; assert "memory" in payload; assert "artifact_paths" in payload; print("[gepa-memory-preview-smoke] remote preview contract passed:", payload["status"], payload["source"])' /tmp/barred-fleet-gepa-memory-preview.json

verify-gepa-memory-preview: gepa-memory-preview-local gepa-memory-preview-smoke

verify-demo:
	@echo "[verify-demo] checking unauthenticated /demo is private"
	@status="$$(curl -sS -o /tmp/barred-fleet-demo-unauth.html -w '%{http_code}' "$(DEMO_URL)/demo")"; \
	if [ "$$status" != "403" ]; then \
		echo "[verify-demo] expected unauthenticated /demo HTTP 403, got $$status"; \
		exit 1; \
	fi
	@echo "[verify-demo] checking authenticated /demo/report contract"
	@token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-demo-report.json -w '%{http_code}' -H "Authorization: Bearer $$token" "$(DEMO_URL)/demo/report?run_id=$(DEMO_RUN_ID)")"; \
	if [ "$$status" != "200" ]; then \
		echo "[verify-demo] expected authenticated /demo/report HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; payload = json.load(open(sys.argv[1])); assert payload["status"] == "ok"; assert payload["run_id"] == "$(DEMO_RUN_ID)"; assert payload["b_gate"]["passed"] is True; assert payload["b_gate"]["accepted_rows"] == 5; assert payload["b_gate"]["total_rows"] == 5; assert payload["b_gate"]["verifier_parse_ok_rate"] == 1.0; assert payload["b_gate"]["verifier_pass_rate"] == 0.75; assert payload["deterministic_eval"]["score"] == 1.0; assert payload["provenance"]["chain"][0]["system"].startswith("Firestore metadata:"); print("[verify-demo] /demo/report contract passed")' /tmp/barred-fleet-demo-report.json
	@$(MAKE) product-report-smoke
	@$(MAKE) demo-smoke

verify-fresh-demo:
	@echo "[verify-fresh-demo] checking authenticated fresh dry-run contract"
	@token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-fresh-dry-run.json -w '%{http_code}' -X POST -H "Authorization: Bearer $$token" -H "Content-Type: application/json" "$(DEMO_URL)/runs/fresh-demo" -d '{"seed_id":"fixture:first","run_id":"fresh-demo-cloud-dry-run","dry_run":true,"max_attempts":1}')"; \
	if [ "$$status" != "200" ]; then \
		echo "[verify-fresh-demo] expected fresh dry-run HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; payload = json.load(open(sys.argv[1])); assert payload["status"] == "planned"; assert payload["run_id"] == "fresh-demo-cloud-dry-run"; assert payload["dry_run"] is True; assert payload["limits"]["max_attempts"] == 1; assert payload["artifact_paths"]["input_path"].endswith("training_corpus.jsonl"); print("[verify-fresh-demo] dry-run contract passed")' /tmp/barred-fleet-fresh-dry-run.json
	@echo "[verify-fresh-demo] checking live execution refuses safely"
	@token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-fresh-live-refusal.json -w '%{http_code}' -X POST -H "Authorization: Bearer $$token" -H "Content-Type: application/json" "$(DEMO_URL)/runs/fresh-demo" -d '{"seed_id":"fixture:first","run_id":"fresh-demo-cloud-live-refusal","dry_run":false,"max_attempts":1}')"; \
	if [ "$$status" != "200" ]; then \
		echo "[verify-fresh-demo] expected fresh live-refusal HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; payload = json.load(open(sys.argv[1])); model_armor = payload["model_armor"]; seed_screening = model_armor["seed_screening"]; gateway = payload["agent_gateway"]; assert payload["status"] == "attention_required"; assert payload["run_id"] == "fresh-demo-cloud-live-refusal"; assert payload["required_env"] == "BARRED_ENABLE_LIVE_FRESH_DEBATE=true"; assert model_armor["status"] == "configured"; assert model_armor["mode"] == "cloud_model_armor"; assert seed_screening["status"] == "passed"; assert seed_screening["checked"] is True; assert seed_screening["blocked"] is False; assert seed_screening["filter_match_state"] == "NO_MATCH_FOUND"; assert seed_screening["invocation_result"] == "SUCCESS"; assert seed_screening["input_text_stored"] is False; assert seed_screening["template_name"].endswith("/templates/barred-seed-screen-v1"); assert gateway["status"] == "configured"; assert gateway["mode"] in {"local_policy", "cloud_agent_gateway"}; assert gateway["decision_authority"] == "routing_and_egress_only"; assert gateway["egress_decision"]["blocked"] is False; assert gateway.get("cloud_control_plane", {"checked": True})["checked"] is True; print("[verify-fresh-demo] live-refusal safety contracts passed")' /tmp/barred-fleet-fresh-live-refusal.json
	@echo "[verify-fresh-demo] checking Agent Gateway guaranteed-block smoke"
	@token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-fresh-agent-gateway-block.json -w '%{http_code}' -X POST -H "Authorization: Bearer $$token" -H "Content-Type: application/json" "$(DEMO_URL)/runs/fresh-demo" -d '{"seed_id":"fixture:first","run_id":"fresh-demo-agent-gateway-block","dry_run":false,"max_attempts":1,"model_routes":{"generator":"unapproved/provider"}}')"; \
	if [ "$$status" != "200" ]; then \
		echo "[verify-fresh-demo] expected Agent Gateway block HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; payload = json.load(open(sys.argv[1])); gateway = payload["agent_gateway"]; assert payload["status"] == "attention_required"; assert payload["run_id"] == "fresh-demo-agent-gateway-block"; assert payload["error_category"] == "egress_policy"; assert payload["error"] == "agent gateway blocked live execution"; assert gateway["status"] == "blocked"; assert gateway["mode"] in {"local_policy", "cloud_agent_gateway"}; assert gateway["decision_authority"] == "routing_and_egress_only"; assert gateway["egress_decision"]["blocked"] is True; assert gateway["egress_decision"]["reason"] == "model_route_blocked"; assert gateway["model_route_policy"]["rejected_routes"] == ["unapproved/provider"]; assert gateway.get("cloud_control_plane", {"checked": True})["checked"] is True; print("[verify-fresh-demo] Agent Gateway block contract passed")' /tmp/barred-fleet-fresh-agent-gateway-block.json
	@echo "[verify-fresh-demo] checking Model Armor guaranteed-block smoke"
	@token="$$(gcloud auth print-identity-token)"; \
	status="$$(curl -sS -o /tmp/barred-fleet-fresh-model-armor-block.json -w '%{http_code}' -X POST -H "Authorization: Bearer $$token" -H "Content-Type: application/json" "$(DEMO_URL)/runs/fresh-demo" -d '{"seed_id":"smoke:model-armor-block","run_id":"fresh-demo-model-armor-block","dry_run":false,"max_attempts":1}')"; \
	if [ "$$status" != "200" ]; then \
		echo "[verify-fresh-demo] expected Model Armor block HTTP 200, got $$status"; \
		exit 1; \
	fi; \
	python3 -c 'import json, sys; payload = json.load(open(sys.argv[1])); model_armor = payload["model_armor"]; seed_screening = model_armor["seed_screening"]; assert payload["status"] == "attention_required"; assert payload["run_id"] == "fresh-demo-model-armor-block"; assert payload["error_category"] == "content_safety"; assert payload["error"] == "model armor seed screening blocked live execution"; assert model_armor["status"] == "configured"; assert model_armor["mode"] == "cloud_model_armor"; assert seed_screening["status"] == "blocked"; assert seed_screening["checked"] is True; assert seed_screening["blocked"] is True; assert seed_screening["filter_match_state"] == "MATCH_FOUND"; assert seed_screening["invocation_result"] == "SUCCESS"; assert seed_screening["input_text_stored"] is False; assert seed_screening["template_name"].endswith("/templates/barred-seed-screen-v1"); print("[verify-fresh-demo] Model Armor block contract passed")' /tmp/barred-fleet-fresh-model-armor-block.json

verify-packaged-stack:
	uv run python scripts/verify_packaged_stack.py

eval-artifact-gate-generate:
	agents-cli eval generate --dataset tests/eval/datasets/barred-artifact-gate-dataset.json --output artifacts/traces/barred-artifact-gate --url $(ADK_EVAL_URL) --app-name $(ADK_APP_NAME) --concurrency $(ADK_EVAL_CONCURRENCY)

eval-artifact-gate-grade:
	agents-cli eval grade --traces artifacts/traces/barred-artifact-gate --output artifacts/grade_results/barred-artifact-gate

eval-artifact-gate-grade-deterministic:
	agents-cli eval grade --traces artifacts/traces/barred-artifact-gate --config tests/eval/eval_config_artifact_gate.yaml --output artifacts/grade_results/barred-artifact-gate-deterministic

eval-report-generate:
	agents-cli eval generate --dataset tests/eval/datasets/barred-report-dataset.json --output artifacts/traces/barred-report --url $(ADK_EVAL_URL) --app-name $(ADK_APP_NAME) --concurrency $(ADK_EVAL_CONCURRENCY)

eval-report-grade-deterministic:
	agents-cli eval grade --traces artifacts/traces/barred-report --config tests/eval/eval_config_report.yaml --output artifacts/grade_results/barred-report-deterministic

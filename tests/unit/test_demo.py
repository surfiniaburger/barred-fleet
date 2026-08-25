import pytest
from fastapi.testclient import TestClient

import app.demo as demo_module
from app.demo import DEMO_PROMPT, DEMO_RUN_ID, build_demo_html, build_demo_report
from app.fast_api_app import app


def test_build_demo_report_returns_curated_b_gate_summary() -> None:
    report = build_demo_report()

    assert report["run_id"] == DEMO_RUN_ID
    assert report["demo_prompt"] == DEMO_PROMPT
    assert report["status"] == "ok"
    assert report["b_gate"]["passed"] is True
    assert report["b_gate"]["accepted_rows"] == 5
    assert report["b_gate"]["verifier_parse_ok_rate"] == 1.0
    assert report["b_gate"]["selected_metrics"]["accepted_rows"] == 5
    scorecard = report["b_gate"]["invariant_scorecard"]
    assert scorecard["available"] is True
    assert scorecard["rows"][0] == {
        "key": "total_rows",
        "label": "Total accepted corpus rows",
        "format": "integer",
        "direction": "context",
        "value": 5,
        "available": True,
    }
    assert any(
        row["key"] == "accepted_corpus_logic_error_rate"
        for row in scorecard["rows"]
    )
    assert report["deterministic_eval"]["score"] == 1.0
    assert report["model_armor"]["status"] == "not_configured"
    assert report["agent_gateway"]["status"] == "not_configured"
    assert report["provenance"]["artifact_paths"]["input_path"] == (
        "training_corpus_calibrated_pecan.jsonl"
    )
    assert report["provenance"]["artifact_registry"]["corpus"]["path"] == (
        "training_corpus_calibrated_pecan.jsonl"
    )
    assert report["provenance"]["artifact_registry"]["attempts"]["available"] is True
    assert (
        report["provenance"]["artifact_registry"]["deterministic_eval_result"][
            "available"
        ]
        is True
    )
    assert (
        report["provenance"]["artifact_registry"]["diagnostic_receipt"]["available"]
        is False
    )
    assert report["provenance"]["chain"] == [
        {
            "step": "1. Run metadata",
            "system": "Packaged local registry",
            "evidence": DEMO_RUN_ID,
        },
        {
            "step": "2. Artifact storage",
            "system": "Packaged local artifacts",
            "evidence": "training_corpus_calibrated_pecan.jsonl",
        },
        {
            "step": "3. Deterministic gate",
            "system": "BARRED offline B-gate",
            "evidence": "pass",
        },
        {
            "step": "4. Agent role",
            "system": "ADK root agent",
            "evidence": "narrates computed facts; does not decide acceptance",
        },
    ]


def test_metadata_source_label_prefers_firestore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo_module, "RUN_REGISTRY_FIRESTORE_COLLECTION", "barred_runs")
    monkeypatch.setattr(demo_module, "RUN_REGISTRY_FIRESTORE_PROJECT", "gem-creation")
    monkeypatch.setattr(demo_module, "RUN_REGISTRY_FIRESTORE_DATABASE", "barred-fleet")

    assert demo_module._metadata_source_label() == (
        "Firestore metadata: gem-creation/barred-fleet/barred_runs"
    )


def test_build_demo_html_contains_no_external_asset_dependencies() -> None:
    html = build_demo_html()

    assert DEMO_RUN_ID in html
    assert DEMO_PROMPT in html
    assert "/demo/report" in html
    assert "Provenance Chain" in html
    assert "metadata → artifacts → deterministic gate → agent narration" in html
    assert "Decision Breakdown" in html
    assert "Accepted rows" in html
    assert "Rejected rows" in html
    assert "Generator/debater lane" in html
    assert "Artifact facts are computed by deterministic tools" in html
    assert "Fresh Debate Seed Preview" in html
    assert "Packaged Seed Manifest" in html
    assert "Local Safety Policy" in html
    assert "This deterministic policy gates the demo" in html
    assert "/seeds/manifest" in html
    assert "loadSeedManifest()" in html
    assert "allowlisted only" in html
    assert "safety_policy" in html
    assert "Seed allowlist" in html
    assert "Arbitrary paths" in html
    assert "Raw seed text" in html
    assert "Live gates" in html
    assert "fixture:first" in html
    assert "cve500:N" in html
    assert "/runs/fresh-demo" in html
    assert 'dryRun ? "/runs/fresh-demo" : "/runs"' in html
    assert "async_mode: !dryRun" in html
    assert "loadProductRunReport(runId)" in html
    assert "pollRunStatus(data.run_id)" in html
    assert 'fetch(`/runs/${encodeURIComponent(runId)}/report`' in html
    assert 'fetch(`/runs/${encodeURIComponent(runId)}`' in html
    assert "dry_run: dryRun" in html
    assert "requestFreshDebate(true)" in html
    assert "requestFreshDebate(false)" in html
    assert "Run bounded live debate" in html
    assert "Refresh latest run status" in html
    assert "const maxAttempts = 80" in html
    assert "Still running after 120s" in html
    assert "Still running; refresh status" in html
    assert "setButtonLoading(liveButton, true" in html
    assert "Running bounded live debate" in html
    assert "refreshLatestRunStatus()" in html
    assert "TERMINAL_RUN_STATES" in html
    assert "TERMINAL_RUN_STATES.includes(lifecycle?.status)" in html
    assert "Live Debate Result" in html
    assert "Production Safety Controls" in html
    assert "Live Invariant Scorecard" in html
    assert "Invariant Scorecard" in html
    assert "renderInvariantScorecard" in html
    assert "Per-run deterministic B-gate metrics only" in html
    assert "Model Armor screens content safety" in html
    assert "Agent Gateway controls model/tool egress" in html
    assert "renderSafetyControls(reportData, lifecycleData)" in html
    assert "Model Armor status" in html
    assert "Model Armor authority" in html
    assert "Seed screening" in html
    assert "Seed text stored" in html
    assert "Agent Gateway status" in html
    assert "Gateway authority" in html
    assert "Egress decision" in html
    assert "Model route policy" in html
    assert "Tool egress policy" in html
    assert "Acceptance authority" in html
    assert "BARRED deterministic B-gate" in html
    assert "Lifecycle phase" in html
    assert "Running debate" in html
    assert "Blocked: live disabled" in html
    assert "Duration" in html
    assert "Artifact promotion" in html
    assert "Artifact report" in html
    assert "Safety policy" in html
    assert "Safety receipt" in html
    assert "Live flags checked" in html
    assert "Model Armor" in html
    assert "Agent Gateway" in html
    assert "not_configured" in html
    assert "Diagnostic receipt" in html
    assert "artifact_registry" in html
    assert "Verifier parse OK" in html
    assert "Deterministic eval" in html
    assert "B-gate pass/fail" in html
    assert "backend flags still gate that path" in html
    assert "https://" not in html


def test_demo_report_endpoint_returns_curated_report() -> None:
    with TestClient(app) as client:
        response = client.get("/demo/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == DEMO_RUN_ID
    assert payload["b_gate"]["passed"] is True
    assert payload["b_gate"]["accepted_rows"] == 5
    assert payload["b_gate"]["total_rows"] == 5
    assert payload["b_gate"]["verifier_parse_ok_rate"] == 1.0
    assert payload["b_gate"]["verifier_pass_rate"] == 0.75
    assert payload["b_gate"]["selected_metrics"]["accepted_rows"] == 5
    assert payload["b_gate"]["invariant_scorecard"]["available"] is True
    assert {
        row["key"] for row in payload["b_gate"]["invariant_scorecard"]["rows"]
    } >= {
        "b0_structural_completeness_pass_rate",
        "b1_unsupported_in_accepted_rate",
        "b1_inconclusive_in_accepted_rate",
        "b2_anchor_match_rate",
        "accepted_attempt_logic_error_rate",
        "accepted_corpus_logic_error_rate",
    }
    assert payload["deterministic_eval"]["score"] == 1.0
    assert payload["model_armor"]["status"] == "not_configured"
    assert payload["agent_gateway"]["status"] == "not_configured"
    assert payload["attempts"]["decisions"] == {"accepted": 5, "rejected": 12}


def test_demo_report_endpoint_accepts_run_id_query() -> None:
    with TestClient(app) as client:
        response = client.get("/demo/report", params={"run_id": "unknown-run"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "unknown-run"
    assert payload["status"] == "attention_required"
    assert payload["b_gate"]["status"] == "error"
    assert "input_path is required" in payload["b_gate"]["error"]


def test_demo_page_endpoint_serves_html() -> None:
    with TestClient(app) as client:
        response = client.get("/demo")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Deterministic vulnerability acceptance" in response.text

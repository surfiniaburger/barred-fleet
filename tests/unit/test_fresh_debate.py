import pytest
from fastapi.testclient import TestClient

import app.fresh_debate as fresh_debate_module
import app.tools as tools_module
from app.agent_gateway import CloudAgentGateway, LocalPolicyAgentGateway
from app.debate_stack import DebateStackHandle
from app.fast_api_app import app
from app.fresh_debate import (
    FreshDebateRequest,
    build_packaged_seed_manifest,
    run_fresh_debate,
    run_fresh_debate_async,
)
from app.model_armor import CloudModelArmorTextSafetyScreen


def _write_cve500_seeds(tmp_path, rows: list[dict[str, str]]) -> None:
    seed_dir = tmp_path / "scenarios" / "debate"
    seed_dir.mkdir(parents=True)
    seed_path = seed_dir / "cve_seeds_500.jsonl"
    seed_path.write_text(
        "\n".join(fresh_debate_module.json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


class FakeStackContext:
    def __enter__(self):
        return DebateStackHandle(
            judge_url="http://127.0.0.1:19009",
            started=True,
        )

    def __exit__(self, *_exc_info):
        return False


class FakeAgentGatewayClient:
    def get_agent_gateway(self, *, gateway_resource: str):
        raise RuntimeError(f"unreachable: {gateway_resource}")


class BlockingSeedScreen:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def screen_text(self, *, text: str, context: str) -> dict:
        self.calls.append({"text": text, "context": context})
        return {
            "status": "configured",
            "control": "model_armor",
            "decision_authority": "content_safety_only",
            "seed_screening": {
                "status": "blocked",
                "checked": True,
                "blocked": True,
                "kind": "seed",
            },
            "artifact_screening": {
                "status": "not_started",
                "checked": False,
                "blocked": False,
                "kind": "artifact",
            },
            "input_text_stored": False,
        }


class FakeCloudModelArmorClient:
    def sanitize_user_prompt_text(self, *, template_name: str, text: str) -> dict:
        return {
            "sanitization_result": {
                "filter_match_state": "MATCH_FOUND",
                "invocation_result": "SUCCESS",
            }
        }


def test_fresh_debate_disabled_mode_returns_attention_required(
    monkeypatch,
) -> None:
    monkeypatch.delenv("BARRED_ENABLE_FRESH_DEBATE", raising=False)

    response = run_fresh_debate(FreshDebateRequest(seed_id="fixture:first"))

    assert response == {
        "status": "attention_required",
        "run_id": None,
        "error": "fresh debate execution is disabled",
        "required_env": "BARRED_ENABLE_FRESH_DEBATE=true",
    }


def test_fresh_debate_dry_run_returns_bounded_plan(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-demo-test",
            dry_run=True,
            max_attempts=1,
        )
    )

    assert response["status"] == "planned"
    assert response["run_id"] == "fresh-demo-test"
    assert response["dry_run"] is True
    assert response["seed_id"] == "fixture:first"
    assert response["limits"] == {
        "max_attempts": 1,
        "timeout_seconds": 180,
    }
    assert response["model_routes"] == {
        "generator": "vertex_ai/gemini-3.5-flash-lite",
        "judge": "vertex_ai/gemini-3.6-flash",
        "verifier": "vertex_ai/gemini-3.6-flash",
    }
    assert response["safety_policy"]["status"] == "enforced"
    assert response["safety_policy"]["seed_allowlist"] == [
        "fixture:first",
        "cve500:N",
        "smoke:model-armor-block",
    ]
    assert response["safety_policy"]["arbitrary_seed_paths_allowed"] is False
    assert response["safety_policy"]["raw_seed_text_exposed"] is False
    assert response["safety_policy"]["max_attempts"] == {
        "min": 1,
        "max": 3,
        "live_default_max": 1,
    }
    assert response["safety_receipt"] == {
        "status": "enforced",
        "seed_id": "fixture:first",
        "seed_selector_allowed": True,
        "arbitrary_paths_allowed": False,
        "raw_seed_text_exposed": False,
        "max_attempts": 1,
        "live_execution_flags_checked": False,
        "live_execution_enabled": False,
        "internal_debate_stack_enabled": False,
    }
    assert response["artifact_paths"]["run_dir"].endswith(
        "/tmp/barred-fleet-runs/fresh-demo-test"
    )
    assert response["artifact_paths"]["attempts_path"].endswith("attempts.jsonl")


def test_fresh_debate_dry_run_accepts_cve500_seed_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_DEBATE_RUNTIME_ROOT", str(tmp_path))
    _write_cve500_seeds(
        tmp_path,
        [
            {
                "topic": "first code",
                "predicate": "first predicate",
                "language": "c",
                "original_safety": "vulnerable",
            },
            {
                "topic": "second code",
                "predicate": "second predicate",
                "language": "cpp",
                "original_safety": "safe",
            },
        ],
    )

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="cve500:1",
            run_id="fresh-demo-cve500-test",
            dry_run=True,
        )
    )

    assert response["status"] == "planned"
    assert response["seed_id"] == "cve500:1"
    assert response["seed_metadata"] == {
        "seed_id": "cve500:1",
        "source": "cve500",
        "source_file": "scenarios/debate/cve_seeds_500.jsonl",
        "index": 1,
        "language": "cpp",
        "original_safety": "safe",
        "predicate_sha256": response["seed_metadata"]["predicate_sha256"],
        "topic_sha256": response["seed_metadata"]["topic_sha256"],
    }
    assert len(response["seed_metadata"]["predicate_sha256"]) == 64
    assert len(response["seed_metadata"]["topic_sha256"]) == 64


def test_fresh_debate_dry_run_accepts_model_armor_block_smoke_seed(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="smoke:model-armor-block",
            run_id="fresh-demo-model-armor-smoke",
            dry_run=True,
        )
    )

    assert response["status"] == "planned"
    assert response["seed_id"] == "smoke:model-armor-block"
    assert response["seed_metadata"]["source"] == "smoke"
    assert response["seed_metadata"]["source_file"] == (
        "packaged synthetic safety smoke seed"
    )
    assert response["seed_metadata"]["original_safety"] == "blocked_smoke"
    assert response["seed_metadata"]["language"] == "text"
    assert len(response["seed_metadata"]["predicate_sha256"]) == 64
    assert len(response["seed_metadata"]["topic_sha256"]) == 64


def test_packaged_seed_manifest_reports_allowlisted_sources(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BARRED_DEBATE_RUNTIME_ROOT", str(tmp_path))
    _write_cve500_seeds(
        tmp_path,
        [
            {"topic": "first code", "predicate": "first predicate"},
            {"topic": "second code", "predicate": "second predicate"},
        ],
    )
    fixture_path = tmp_path / "fixture.jsonl"
    fixture_path.write_text(
        fresh_debate_module.json.dumps(
            {"topic": "fixture code", "predicate": "fixture predicate"}
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BARRED_FRESH_DEBATE_SEEDS_PATH", str(fixture_path))

    manifest = build_packaged_seed_manifest()

    assert manifest["status"] == "ok"
    assert manifest["sources"]["fixture"]["selector"] == "fixture:first"
    assert manifest["sources"]["fixture"]["count"] == 1
    assert manifest["sources"]["fixture"]["sha256"]
    assert manifest["sources"]["cve500"]["selector"] == "cve500:N"
    assert manifest["sources"]["cve500"]["count"] == 2
    assert manifest["sources"]["cve500"]["source_file"] == (
        "scenarios/debate/cve_seeds_500.jsonl"
    )
    assert manifest["sources"]["cve500"]["sha256"]
    assert manifest["sources"]["smoke"]["selector"] == "smoke:model-armor-block"
    assert manifest["sources"]["smoke"]["count"] == 1
    assert manifest["sources"]["smoke"]["sha256"]
    assert manifest["selection_policy"] == {
        "allowlisted_only": True,
        "arbitrary_paths_allowed": False,
        "raw_seed_text_exposed": False,
    }
    assert manifest["safety_policy"]["status"] == "enforced"
    assert manifest["safety_policy"]["seed_allowlist"] == [
        "fixture:first",
        "cve500:N",
        "smoke:model-armor-block",
    ]
    assert manifest["safety_policy"]["arbitrary_seed_paths_allowed"] is False
    assert manifest["safety_policy"]["raw_seed_text_exposed"] is False


def test_seed_manifest_route_returns_packaged_sources() -> None:
    with TestClient(app) as client:
        response = client.get("/seeds/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["sources"]["fixture"]["selector"] == "fixture:first"
    assert payload["sources"]["cve500"]["selector"] == "cve500:N"
    assert payload["sources"]["cve500"]["count"] >= 500
    assert payload["selection_policy"]["allowlisted_only"] is True
    assert payload["safety_policy"]["status"] == "enforced"
    assert payload["safety_policy"]["seed_allowlist"] == [
        "fixture:first",
        "cve500:N",
        "smoke:model-armor-block",
    ]


def test_fresh_debate_rejects_unknown_seed(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    response = run_fresh_debate(FreshDebateRequest(seed_id="unknown"))

    assert response["status"] == "attention_required"
    assert response["error"] == "unknown seed_id: unknown"


@pytest.mark.parametrize("seed_id", ["cve500:", "cve500:-1", "cve500:abc"])
def test_fresh_debate_rejects_malformed_cve500_seed_id(
    monkeypatch,
    seed_id,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    response = run_fresh_debate(FreshDebateRequest(seed_id=seed_id))

    assert response["status"] == "attention_required"
    assert response["error"] == f"unknown seed_id: {seed_id}"


def test_fresh_debate_rejects_out_of_range_cve500_seed(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_DEBATE_RUNTIME_ROOT", str(tmp_path))
    _write_cve500_seeds(
        tmp_path,
        [{"topic": "only code", "predicate": "only predicate", "language": "c"}],
    )

    response = run_fresh_debate(FreshDebateRequest(seed_id="cve500:7"))

    assert response["status"] == "attention_required"
    assert response["error"].endswith("does not contain seed index 7")


def test_fresh_debate_rejects_unbounded_limits(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    response = run_fresh_debate(
        FreshDebateRequest(seed_id="fixture:first", max_attempts=4)
    )

    assert response["status"] == "attention_required"
    assert response["error"] == "max_attempts must be between 1 and 3"


def test_fresh_debate_rejects_unsafe_run_id(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    response = run_fresh_debate(
        FreshDebateRequest(seed_id="fixture:first", run_id="../escape")
    )

    assert response["status"] == "attention_required"
    assert response["error"] == "run_id contains unsupported characters"


def test_fresh_debate_live_mode_requires_separate_env_flag(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.delenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", raising=False)

    response = run_fresh_debate(
        FreshDebateRequest(seed_id="fixture:first", dry_run=False)
    )

    assert response["status"] == "attention_required"
    assert response["run_id"]
    assert response["error"] == "live fresh debate execution is disabled"
    assert response["required_env"] == "BARRED_ENABLE_LIVE_FRESH_DEBATE=true"
    assert response["model_armor"]["status"] == "not_configured"
    assert response["model_armor"]["seed_screening"]["checked"] is False
    assert response["model_armor"]["seed_screening"]["blocked"] is False
    assert response["agent_gateway"]["status"] == "not_configured"
    assert response["agent_gateway"]["egress_decision"]["blocked"] is False


def test_fresh_debate_live_mode_requires_internal_stack_flag(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.delenv("BARRED_START_INTERNAL_DEBATE_STACK", raising=False)

    response = run_fresh_debate(
        FreshDebateRequest(seed_id="fixture:first", dry_run=False),
        runner=lambda _plan: {"status": "should-not-run"},
    )

    assert response["status"] == "attention_required"
    assert response["run_id"]
    assert response["error"] == "internal debate stack startup is disabled"
    assert response["required_env"] == "BARRED_START_INTERNAL_DEBATE_STACK=true"
    assert response["model_armor"]["status"] == "not_configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is False
    assert response["agent_gateway"]["status"] == "not_configured"
    assert response["agent_gateway"]["egress_decision"]["blocked"] is False


def test_fresh_debate_live_mode_caps_max_attempts_by_default(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")

    response = run_fresh_debate(
        FreshDebateRequest(seed_id="fixture:first", dry_run=False, max_attempts=2),
        runner=lambda _plan: {"status": "should-not-run"},
    )

    assert response["status"] == "attention_required"
    assert response["run_id"]
    assert response["error"] == "live fresh debate max_attempts must be <= 1"
    assert response["model_armor"]["status"] == "not_configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is False
    assert response["agent_gateway"]["status"] == "not_configured"
    assert response["agent_gateway"]["egress_decision"]["blocked"] is False


def test_fresh_debate_local_agent_gateway_allows_before_live_refusal(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.delenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", raising=False)
    gateway = LocalPolicyAgentGateway()

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-agent-gateway-pass-refusal",
            dry_run=False,
        ),
        agent_gateway=gateway,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-agent-gateway-pass-refusal"
    assert response["required_env"] == "BARRED_ENABLE_LIVE_FRESH_DEBATE=true"
    assert response["agent_gateway"]["status"] == "configured"
    assert response["agent_gateway"]["decision_authority"] == (
        "routing_and_egress_only"
    )
    assert response["agent_gateway"]["egress_decision"]["blocked"] is False
    assert response["agent_gateway"]["model_route_policy"]["blocked"] is False
    assert response["agent_gateway"]["tool_egress_policy"]["blocked"] is False


def test_fresh_debate_local_agent_gateway_blocks_before_runner(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    gateway = LocalPolicyAgentGateway()

    def should_not_run(_plan):
        raise AssertionError("blocked egress must not reach the live runner")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-agent-gateway-blocked",
            dry_run=False,
            model_routes={"generator": "unapproved/provider"},
        ),
        runner=should_not_run,
        agent_gateway=gateway,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-agent-gateway-blocked"
    assert response["error_category"] == "egress_policy"
    assert response["error"] == "agent gateway blocked live execution"
    assert response["agent_gateway"]["status"] == "blocked"
    assert response["agent_gateway"]["egress_decision"]["blocked"] is True
    assert response["agent_gateway"]["egress_decision"]["reason"] == (
        "model_route_blocked"
    )
    assert response["agent_gateway"]["model_route_policy"]["rejected_routes"] == [
        "unapproved/provider"
    ]


def test_fresh_debate_cloud_agent_gateway_error_blocks_before_runner(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    gateway = CloudAgentGateway(
        project_id="gem-creation",
        location_id="us-east1",
        gateway_id="barred-egress-v1",
        client=FakeAgentGatewayClient(),
    )

    def should_not_run(_plan):
        raise AssertionError("blocked cloud gateway must not reach the live runner")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-cloud-agent-gateway-error",
            dry_run=False,
        ),
        runner=should_not_run,
        agent_gateway=gateway,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-cloud-agent-gateway-error"
    assert response["error_category"] == "egress_policy"
    assert response["error"] == "agent gateway blocked live execution"
    assert response["agent_gateway"]["status"] == "error"
    assert response["agent_gateway"]["mode"] == "cloud_agent_gateway"
    assert response["agent_gateway"]["egress_decision"]["blocked"] is True
    assert response["agent_gateway"]["egress_decision"]["reason"] == (
        "cloud_agent_gateway_unavailable"
    )


@pytest.mark.asyncio
async def test_fresh_debate_async_live_mode_uses_injected_runner(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")

    async def fake_runner(plan):
        return {
            "status": "ok",
            "run_id": plan.run_id,
            "execution": {
                "fresh": True,
                "dry_run": False,
                "seed_id": plan.seed_id,
                "artifact_scope": "tmp",
                "timeout_seconds": plan.timeout_seconds,
                "judge_url": plan.judge_url,
            },
            "artifact_paths": plan.artifact_paths,
        }

    response = await run_fresh_debate_async(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-demo-async-test",
            dry_run=False,
        ),
        runner=fake_runner,
    )

    assert response["status"] == "ok"
    assert response["run_id"] == "fresh-demo-async-test"
    assert response["execution"] == {
        "fresh": True,
        "dry_run": False,
        "seed_id": "fixture:first",
        "artifact_scope": "tmp",
        "timeout_seconds": 180,
        "judge_url": "http://127.0.0.1:9009",
    }


def test_fresh_debate_fake_runner_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    monkeypatch.setenv("BARRED_FRESH_DEBATE_TMP_DIR", str(tmp_path))

    def fake_runner(plan):
        return {
            "status": "ok",
            "run_id": plan.run_id,
            "execution": {
                "fresh": True,
                "dry_run": False,
                "seed_id": plan.seed_id,
                "artifact_scope": "tmp",
                "timeout_seconds": plan.timeout_seconds,
            },
            "artifact_paths": plan.artifact_paths,
            "b_gate": {"status": "ok", "passed": True},
        }

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-demo-live-test",
            dry_run=False,
        ),
        runner=fake_runner,
    )

    assert response["status"] == "ok"
    assert response["run_id"] == "fresh-demo-live-test"
    assert response["execution"]["fresh"] is True
    assert response["b_gate"]["passed"] is True
    assert response["model_armor"]["status"] == "not_configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is False


def test_fresh_debate_live_seed_screen_blocks_before_runner(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    screen = BlockingSeedScreen()

    def should_not_run(_plan):
        raise AssertionError("blocked seed must not reach the live runner")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-seed-screen-blocked",
            dry_run=False,
        ),
        runner=should_not_run,
        safety_screen=screen,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-seed-screen-blocked"
    assert response["error_category"] == "content_safety"
    assert response["error"] == "model armor seed screening blocked live execution"
    assert response["model_armor"]["status"] == "configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is True
    assert response["model_armor"]["input_text_stored"] is False
    assert screen.calls[0]["context"] == "fresh_debate.seed"


def test_fresh_debate_env_local_blocklist_blocks_before_runner(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    monkeypatch.setenv("BARRED_MODEL_ARMOR_MODE", "local_blocklist")
    monkeypatch.setenv("BARRED_MODEL_ARMOR_BLOCKLIST", "MDIO")

    def should_not_run(_plan):
        raise AssertionError("blocked seed must not reach the live runner")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-env-blocklist-blocked",
            dry_run=False,
        ),
        runner=should_not_run,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-env-blocklist-blocked"
    assert response["error_category"] == "content_safety"
    assert response["model_armor"]["status"] == "configured"
    assert response["model_armor"]["mode"] == "local_blocklist"
    assert response["model_armor"]["seed_screening"]["checked"] is True
    assert response["model_armor"]["seed_screening"]["blocked"] is True


def test_fresh_debate_cloud_model_armor_blocks_before_runner(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    screen = CloudModelArmorTextSafetyScreen(
        project_id="gem-creation",
        location_id="us-east1",
        template_id="barred-template",
        client=FakeCloudModelArmorClient(),
    )

    def should_not_run(_plan):
        raise AssertionError("blocked seed must not reach the live runner")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-cloud-model-armor-blocked",
            dry_run=False,
        ),
        runner=should_not_run,
        safety_screen=screen,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-cloud-model-armor-blocked"
    assert response["error_category"] == "content_safety"
    assert response["model_armor"]["status"] == "configured"
    assert response["model_armor"]["mode"] == "cloud_model_armor"
    assert response["model_armor"]["seed_screening"]["checked"] is True
    assert response["model_armor"]["seed_screening"]["blocked"] is True
    assert response["model_armor"]["seed_screening"]["filter_match_state"] == (
        "MATCH_FOUND"
    )


def test_fresh_debate_fake_runner_failure_returns_attention(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")

    def failing_runner(_plan):
        raise RuntimeError("model route unavailable")

    response = run_fresh_debate(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-demo-failure-test",
            dry_run=False,
        ),
        runner=failing_runner,
    )

    assert response["status"] == "attention_required"
    assert response["run_id"] == "fresh-demo-failure-test"
    assert response["error"] == "fresh debate runner failed: model route unavailable"
    assert response["model_armor"]["status"] == "not_configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is False


@pytest.mark.asyncio
async def test_fresh_debate_async_default_seed_screen_does_not_block(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")

    async def fake_runner(plan):
        return {
            "status": "completed",
            "run_id": plan.run_id,
            "artifact_paths": plan.artifact_paths,
        }

    response = await run_fresh_debate_async(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-seed-screen-default",
            dry_run=False,
        ),
        runner=fake_runner,
    )

    assert response["status"] == "completed"
    assert response["model_armor"]["status"] == "not_configured"
    assert response["model_armor"]["seed_screening"]["blocked"] is False


@pytest.mark.asyncio
async def test_fresh_debate_live_runner_loads_packaged_fixture(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    monkeypatch.setattr(
        fresh_debate_module,
        "start_internal_debate_stack",
        lambda _config: FakeStackContext(),
    )

    async def fake_execute_debate_case(*, payload, judge_url):
        return {
            "status": "completed",
            "judge_url": judge_url,
            "topic": payload["config"]["topic"],
            "predicate": payload["config"]["predicate"],
        }

    monkeypatch.setattr(tools_module, "execute_debate_case", fake_execute_debate_case)

    response = await run_fresh_debate_async(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-demo-packaged-fixture-test",
            dry_run=False,
        )
    )

    assert response["status"] == "completed"
    assert response["execution"]["internal_stack_started"] is True
    assert response["debate_result"]["topic"]
    assert response["debate_result"]["predicate"]
    assert response["fresh_report"]["status"] == "attention_required"
    assert response["fresh_report"]["promotion"]["reason"] == "missing_input_artifact"


@pytest.mark.asyncio
async def test_fresh_debate_live_runner_loads_cve500_seed(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    monkeypatch.setenv("BARRED_DEBATE_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setattr(
        fresh_debate_module,
        "start_internal_debate_stack",
        lambda _config: FakeStackContext(),
    )
    _write_cve500_seeds(
        tmp_path,
        [
            {
                "topic": "selected cve code",
                "predicate": "selected cve predicate",
                "language": "c",
                "original_safety": "vulnerable",
            }
        ],
    )

    async def fake_execute_debate_case(*, payload, judge_url):
        return {
            "status": "completed",
            "judge_url": judge_url,
            "topic": payload["config"]["topic"],
            "predicate": payload["config"]["predicate"],
        }

    monkeypatch.setattr(tools_module, "execute_debate_case", fake_execute_debate_case)

    response = await run_fresh_debate_async(
        FreshDebateRequest(
            seed_id="cve500:0",
            run_id="fresh-demo-cve500-live-test",
            dry_run=False,
        )
    )

    assert response["status"] == "completed"
    assert response["debate_result"]["topic"] == "selected cve code"
    assert response["debate_result"]["predicate"] == "selected cve predicate"
    assert response["execution"]["seed_metadata"]["source"] == "cve500"
    assert response["execution"]["seed_metadata"]["index"] == 0


@pytest.mark.asyncio
async def test_fresh_debate_live_mode_can_start_internal_stack(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_ENABLE_LIVE_FRESH_DEBATE", "true")
    monkeypatch.setenv("BARRED_START_INTERNAL_DEBATE_STACK", "true")
    monkeypatch.setattr(
        fresh_debate_module,
        "_load_fixture_seed",
        lambda _seed_id: {"topic": "code", "predicate": "predicate"},
    )

    stack_configs = []

    def fake_start_internal_debate_stack(config):
        stack_configs.append(config)
        return FakeStackContext()

    async def fake_execute_debate_case(*, payload, judge_url):
        return {
            "status": "completed",
            "judge_url": judge_url,
            "payload_run_id": payload["config"]["run_id"],
            "payload_max_refinements": payload["config"]["max_refinements"],
        }

    monkeypatch.setattr(
        fresh_debate_module,
        "start_internal_debate_stack",
        fake_start_internal_debate_stack,
    )
    monkeypatch.setattr(tools_module, "execute_debate_case", fake_execute_debate_case)

    response = await run_fresh_debate_async(
        FreshDebateRequest(
            seed_id="fixture:first",
            run_id="fresh-demo-stack-test",
            dry_run=False,
            max_attempts=1,
        )
    )

    assert stack_configs
    assert response["status"] == "completed"
    assert response["execution"]["internal_stack_started"] is True
    assert response["execution"]["judge_url"] == "http://127.0.0.1:19009"
    assert response["debate_result"]["payload_run_id"] == "fresh-demo-stack-test"
    assert response["debate_result"]["payload_max_refinements"] == 1


def test_fresh_debate_endpoint_dry_run(monkeypatch) -> None:
    monkeypatch.setenv("BARRED_ENABLE_FRESH_DEBATE", "true")

    with TestClient(app) as client:
        response = client.post(
            "/runs/fresh-demo",
            json={
                "seed_id": "fixture:first",
                "run_id": "fresh-demo-route-test",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "planned"
    assert payload["run_id"] == "fresh-demo-route-test"
    assert payload["artifact_paths"]["input_path"].endswith("training_corpus.jsonl")

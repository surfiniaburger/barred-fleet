from __future__ import annotations

from app.reflection_memory import (
    DIAGNOSTIC_ACCEPTED,
    DIAGNOSTIC_B_GATE_REJECTED,
    DIAGNOSTIC_CONFIGURATION_BLOCKED,
    DIAGNOSTIC_CONTENT_SAFETY_BLOCKED,
    DIAGNOSTIC_EGRESS_POLICY_BLOCKED,
    DIAGNOSTIC_RUNNER_FAILED,
    compile_reflection_memory,
)


def _base_report() -> dict:
    return {
        "run_id": "product-memory-test",
        "status": "ok",
        "lifecycle": {
            "status": "completed",
            "error_category": "",
        },
        "seed_id": "fixture:first",
        "seed_metadata": {
            "seed_id": "fixture:first",
            "source_file": "scenarios/debate/cve_seeds_test.jsonl",
            "index": 0,
            "language": "c",
            "predicate_family": "BUFFER_OVERFLOW",
        },
        "model_routes": {
            "generator": "vertex_ai/gemini-3.5-flash-lite",
            "judge": "vertex_ai/gemini-3.6-flash",
            "verifier": "vertex_ai/gemini-3.6-flash",
        },
        "model_armor": {
            "status": "configured",
            "mode": "cloud_model_armor",
            "seed_screening": {"checked": True, "blocked": False},
        },
        "agent_gateway": {
            "status": "configured",
            "mode": "cloud_agent_gateway",
            "egress_decision": {"checked": True, "blocked": False},
        },
        "b_gate": {
            "available": True,
            "passed": True,
            "selected_metrics": {
                "verifier_parse_ok_rate": 1.0,
                "verifier_pass_rate": 0.75,
            },
        },
        "deterministic_eval": {
            "available": True,
            "path": "gs://bucket/runs/product-memory-test/deterministic_eval_result.json",
            "score": 1.0,
        },
        "promotion": {
            "status": "promoted",
            "reason": "gcs_and_firestore_written",
        },
        "artifact_registry": {
            "deterministic_eval_result": {
                "path": "gs://bucket/runs/product-memory-test/deterministic_eval_result.json",
                "available": True,
            }
        },
    }


def test_compile_accepted_report_memory() -> None:
    memory = compile_reflection_memory(_base_report())

    assert memory["memory_id"].startswith("sha256:")
    assert memory["source_run_id"] == "product-memory-test"
    assert memory["memory_kind"] == "run_outcome_summary"
    assert memory["diagnostic_bucket"] == DIAGNOSTIC_ACCEPTED
    assert memory["predicate_family"] == "BUFFER_OVERFLOW"
    assert memory["seed_id"] == "fixture:first"
    assert memory["seed_source"] == "scenarios/debate/cve_seeds_test.jsonl"
    assert memory["seed_index"] == 0
    assert memory["b_gate_passed"] is True
    assert memory["promotion_status"] == "promoted"
    assert memory["verifier_parse_ok_rate"] == 1.0
    assert memory["verifier_pass_rate"] == 0.75
    assert memory["safety_controls"] == {
        "model_armor_status": "configured",
        "model_armor_mode": "cloud_model_armor",
        "agent_gateway_status": "configured",
        "agent_gateway_mode": "cloud_agent_gateway",
        "agent_gateway_blocked": False,
    }
    assert "Accepted by deterministic B-gate" in memory["lesson"]
    assert memory["schema_version"] == 1


def test_compile_b_gate_rejected_report_memory() -> None:
    report = _base_report()
    report["b_gate"] = {"available": True, "passed": False, "selected_metrics": {}}
    report["promotion"] = {"status": "not_promoted", "reason": "b_gate_not_passed"}

    memory = compile_reflection_memory(report)

    assert memory["diagnostic_bucket"] == DIAGNOSTIC_B_GATE_REJECTED
    assert memory["b_gate_passed"] is False
    assert memory["promotion_status"] == "not_promoted"
    assert memory["negative_constraints"] == [
        "Do not promote patterns rejected by deterministic B-gate."
    ]


def test_compile_model_armor_blocked_memory() -> None:
    report = _base_report()
    report["lifecycle"] = {"status": "blocked", "error_category": "content_safety"}
    report["model_armor"]["seed_screening"]["blocked"] = True
    report["b_gate"] = {"available": False, "passed": None}

    memory = compile_reflection_memory(report)

    assert memory["diagnostic_bucket"] == DIAGNOSTIC_CONTENT_SAFETY_BLOCKED
    assert memory["negative_constraints"] == ["Do not bypass Model Armor seed screening."]


def test_compile_agent_gateway_blocked_memory() -> None:
    report = _base_report()
    report["lifecycle"] = {"status": "blocked", "error_category": "egress_policy"}
    report["agent_gateway"]["status"] = "blocked"
    report["agent_gateway"]["egress_decision"]["blocked"] = True
    report["b_gate"] = {"available": False, "passed": None}

    memory = compile_reflection_memory(report)

    assert memory["diagnostic_bucket"] == DIAGNOSTIC_EGRESS_POLICY_BLOCKED
    assert memory["safety_controls"]["agent_gateway_blocked"] is True
    assert memory["negative_constraints"] == [
        "Do not route through unapproved model or tool egress."
    ]


def test_compile_configuration_blocked_memory() -> None:
    report = _base_report()
    report["lifecycle"] = {"status": "blocked", "error_category": "configuration"}
    report["b_gate"] = {"available": False, "passed": None}

    memory = compile_reflection_memory(report)

    assert memory["diagnostic_bucket"] == DIAGNOSTIC_CONFIGURATION_BLOCKED
    assert memory["negative_constraints"] == [
        "Do not treat configuration refusal as model evidence."
    ]


def test_compile_runner_failed_memory() -> None:
    report = _base_report()
    report["lifecycle"] = {"status": "failed", "error_category": "runner"}
    report["b_gate"] = {"available": False, "passed": None}

    memory = compile_reflection_memory(report)

    assert memory["diagnostic_bucket"] == DIAGNOSTIC_RUNNER_FAILED
    assert memory["negative_constraints"] == [
        "Do not infer a vulnerability lesson from failed execution."
    ]


def test_memory_id_is_stable() -> None:
    report = _base_report()

    first = compile_reflection_memory(report)
    second = compile_reflection_memory(report)
    changed = compile_reflection_memory({**report, "run_id": "product-memory-test-2"})

    assert first["memory_id"] == second["memory_id"]
    assert first["memory_id"] != changed["memory_id"]


def test_memory_document_is_redacted() -> None:
    report = _base_report()
    report["raw_seed_text"] = "secret seed body"
    report["prompt_text"] = "hidden prompt"
    report["code_text"] = "vulnerable code"

    memory = compile_reflection_memory(report)

    assert memory["raw_prompt_text_stored"] is False
    assert memory["raw_seed_text_stored"] is False
    assert memory["raw_code_text_stored"] is False
    assert "raw_seed_text" not in memory
    assert "prompt_text" not in memory
    assert "code_text" not in memory
    assert "secret seed body" not in repr(memory)
    assert "hidden prompt" not in repr(memory)
    assert "vulnerable code" not in repr(memory)

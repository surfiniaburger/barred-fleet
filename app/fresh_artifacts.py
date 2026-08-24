from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from app.tools import (
    build_artifact_summary,
    build_b_gate_result,
    build_observability_report,
)

PROMOTE_FRESH_RUNS_ENV = "BARRED_PROMOTE_FRESH_RUNS"
PROMOTION_BUCKET_ENV = "BARRED_FRESH_PROMOTION_BUCKET"
RUN_REGISTRY_FIRESTORE_COLLECTION_ENV = "BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION"
RUN_REGISTRY_FIRESTORE_PROJECT_ENV = "BARRED_RUN_REGISTRY_FIRESTORE_PROJECT"
RUN_REGISTRY_FIRESTORE_DATABASE_ENV = "BARRED_RUN_REGISTRY_FIRESTORE_DATABASE"

ArtifactUploader = Callable[[Path, str], None]
FirestoreWriter = Callable[[str, dict[str, Any]], None]


def build_fresh_run_report(
    *,
    run_id: str,
    artifact_paths: Mapping[str, str],
    seed_id: str | None = None,
    seed_metadata: Mapping[str, Any] | None = None,
    model_routes: Mapping[str, str] | None = None,
    safety_policy: Mapping[str, Any] | None = None,
    safety_receipt: Mapping[str, Any] | None = None,
    model_armor: Mapping[str, Any] | None = None,
    agent_gateway: Mapping[str, Any] | None = None,
    max_attempts: int | None = None,
    env: Mapping[str, str] | None = None,
    uploader: ArtifactUploader | None = None,
    firestore_writer: FirestoreWriter | None = None,
) -> dict[str, Any]:
    """Build a deterministic report for a fresh run's temporary artifacts.

    This does not upload artifacts. It decides whether the run is locally ready
    for a later promotion slice.
    """
    environ = os.environ if env is None else env
    run_dir = Path(artifact_paths.get("run_dir", "")).resolve()
    if not str(run_dir):
        return _attention_report(
            run_id=run_id,
            reason="missing_run_dir",
            error="run_dir is required",
            env=environ,
        )

    try:
        paths = _resolve_fresh_artifact_paths(artifact_paths, run_dir=run_dir)
        artifact_summary = build_artifact_summary(
            attempts_path=paths.get("attempts_path", ""),
            checkpoint_path=paths.get("checkpoint_path", ""),
            record_path=paths.get("record_path", ""),
            cassette_path=paths.get("cassette_path", ""),
            base_dir=run_dir,
        )
    except ValueError as exc:
        return _attention_report(
            run_id=run_id,
            reason="invalid_artifact_path",
            error=str(exc),
            env=environ,
        )

    input_path = paths.get("input_path", "")
    if not input_path or not Path(input_path).exists():
        return _missing_input_report(
            run_id=run_id,
            artifact_paths=paths,
            artifact_summary=artifact_summary,
            env=environ,
        )

    report = build_observability_report(
        run_id=run_id,
        input_path=input_path,
        attempts_path=paths.get("attempts_path", ""),
        checkpoint_path=paths.get("checkpoint_path", ""),
        record_path=paths.get("record_path", ""),
        cassette_path=paths.get("cassette_path", ""),
        deterministic_eval_result_path=paths.get("deterministic_eval_result_path", ""),
        base_dir=run_dir,
    )
    if report.get("b_gate", {}).get("passed") is True:
        paths["deterministic_eval_result_path"] = str(
            _write_fresh_b_gate_receipt(
                run_id=run_id,
                run_dir=run_dir,
                b_gate=report.get("b_gate", {}),
            )
        )
        report["artifact_paths"]["deterministic_eval_result_path"] = paths[
            "deterministic_eval_result_path"
        ]
        report["eval_results"]["deterministic"] = {
            "path": paths["deterministic_eval_result_path"],
            "exists": True,
            "summary_metrics": _fresh_b_gate_summary_metrics(
                run_id=run_id,
                b_gate=report.get("b_gate", {}),
            ),
        }
        report["report_checks"]["deterministic_eval_present"] = True
        if all(report["report_checks"].values()):
            report["status"] = "ok"
    report["promotion"] = _promote_if_ready(
        run_id=run_id,
        artifact_paths=paths,
        b_gate=report.get("b_gate", {}),
        seed_id=seed_id,
        seed_metadata=seed_metadata or {},
        model_routes=model_routes or {},
        safety_policy=safety_policy or {},
        safety_receipt=safety_receipt or {},
        model_armor=model_armor or {},
        agent_gateway=agent_gateway or {},
        max_attempts=max_attempts,
        env=environ,
        uploader=uploader,
        firestore_writer=firestore_writer,
    )
    return report


def _write_fresh_b_gate_receipt(
    *,
    run_id: str,
    run_dir: Path,
    b_gate: dict[str, Any],
) -> Path:
    receipt_path = run_dir / "deterministic_eval_result.json"
    receipt_path.write_text(
        json.dumps(
            {
                "summary_metrics": _fresh_b_gate_summary_metrics(
                    run_id=run_id,
                    b_gate=b_gate,
                )
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt_path


def _fresh_b_gate_summary_metrics(
    *,
    run_id: str,
    b_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    selected_metrics = b_gate.get("selected_metrics") or {}
    return [
        {
            "metric_name": "fresh_b_gate_contract",
            "num_cases_total": 1,
            "num_cases_valid": 1 if b_gate.get("passed") is True else 0,
            "num_cases_error": 0 if b_gate.get("passed") is True else 1,
            "mean_score": 1.0 if b_gate.get("passed") is True else 0.0,
            "fixture_run_id": run_id,
            "accepted_rows": selected_metrics.get("accepted_rows"),
            "total_rows": selected_metrics.get("total_rows"),
            "verifier_parse_ok_rate": selected_metrics.get("verifier_parse_ok_rate"),
            "verifier_pass_rate": selected_metrics.get("verifier_pass_rate"),
            "anchor_match_rate": selected_metrics.get("b2_anchor_match_rate"),
        }
    ]


def _resolve_fresh_artifact_paths(
    artifact_paths: Mapping[str, str],
    *,
    run_dir: Path,
) -> dict[str, str]:
    resolved: dict[str, str] = {"run_dir": str(run_dir)}
    for key, path_text in artifact_paths.items():
        if key == "run_dir" or not path_text:
            continue
        path = Path(path_text)
        resolved_path = path.resolve() if path.is_absolute() else (run_dir / path).resolve()
        resolved_path.relative_to(run_dir)
        resolved[key] = str(resolved_path)
    return resolved


def _missing_input_report(
    *,
    run_id: str,
    artifact_paths: dict[str, str],
    artifact_summary: dict[str, Any],
    env: Mapping[str, str],
) -> dict[str, Any]:
    input_path = artifact_paths.get("input_path", "")
    if input_path:
        b_gate = build_b_gate_result(
            input_path=input_path,
            attempts_path=artifact_paths.get("attempts_path", ""),
            base_dir=Path(artifact_paths["run_dir"]),
        )
    else:
        b_gate = {
            "status": "error",
            "passed": False,
            "error": "input_path is required for fresh run promotion",
        }
    return {
        "status": "attention_required",
        "run_id": run_id,
        "artifact_paths": artifact_paths,
        "artifact_summary": artifact_summary,
        "b_gate": {
            "status": b_gate.get("status"),
            "passed": b_gate.get("passed"),
            "failed_checks": b_gate.get("failed_checks", []),
            "selected_metrics": {},
            "error": b_gate.get("error"),
        },
        "model_routing": {"record_models": {}, "attempt_models": {}},
        "eval_results": {"llm": None, "deterministic": None},
        "report_checks": {
            "artifacts_read": artifact_summary["artifact_count"] > 0,
            "b_gate_passed": False,
            "verifier_parse_ok_rate_met": False,
            "deterministic_eval_present": False,
        },
        "promotion": _promotion_decision(
            b_gate_passed=False,
            env=env,
            reason="missing_input_artifact",
        ),
        "notes": [
            "Fresh run artifacts are temporary Cloud Run filesystem artifacts.",
            "No artifact is promoted unless the deterministic B-gate passes.",
        ],
    }


def _attention_report(
    *,
    run_id: str,
    reason: str,
    error: str,
    env: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "status": "attention_required",
        "run_id": run_id,
        "error": error,
        "promotion": _promotion_decision(
            b_gate_passed=False,
            env=env,
            reason=reason,
        ),
    }


def _promotion_decision(
    *,
    b_gate_passed: bool,
    env: Mapping[str, str],
    reason: str = "",
) -> dict[str, Any]:
    enabled = _env_flag(PROMOTE_FRESH_RUNS_ENV, environ=env)
    target_uri = env.get(PROMOTION_BUCKET_ENV, "")
    if reason:
        status = "not_promoted"
        resolved_reason = reason
    elif not b_gate_passed:
        status = "not_promoted"
        resolved_reason = "b_gate_not_passed"
    elif not enabled:
        status = "ready"
        resolved_reason = "promotion_disabled"
    else:
        status = "ready"
        resolved_reason = "promotion_enabled_not_implemented"
    return {
        "enabled": enabled,
        "status": status,
        "reason": resolved_reason,
        "target_uri": target_uri,
    }


def _promote_if_ready(
    *,
    run_id: str,
    artifact_paths: dict[str, str],
    b_gate: dict[str, Any],
    seed_id: str | None,
    seed_metadata: Mapping[str, Any],
    model_routes: Mapping[str, str],
    safety_policy: Mapping[str, Any],
    safety_receipt: Mapping[str, Any],
    model_armor: Mapping[str, Any],
    agent_gateway: Mapping[str, Any],
    max_attempts: int | None,
    env: Mapping[str, str],
    uploader: ArtifactUploader | None,
    firestore_writer: FirestoreWriter | None,
) -> dict[str, Any]:
    if b_gate.get("passed") is not True:
        return _promotion_decision(b_gate_passed=False, env=env)

    enabled = _env_flag(PROMOTE_FRESH_RUNS_ENV, environ=env)
    bucket_uri = env.get(PROMOTION_BUCKET_ENV, "").rstrip("/")
    collection = env.get(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    if not enabled:
        return _promotion_decision(b_gate_passed=True, env=env)
    if not bucket_uri:
        return _ready_without_write(env=env, reason="promotion_bucket_missing")
    if not collection:
        return _ready_without_write(env=env, reason="firestore_collection_missing")

    upload = uploader or _upload_gcs_artifact
    write_firestore = firestore_writer or _write_firestore_run_registry
    try:
        uploaded_paths = _upload_existing_artifacts(
            run_id=run_id,
            artifact_paths=artifact_paths,
            bucket_uri=bucket_uri,
            uploader=upload,
        )
        registry_payload = _build_firestore_registry_payload(
            run_id=run_id,
            uploaded_paths=uploaded_paths,
            b_gate=b_gate,
            seed_id=seed_id,
            seed_metadata=seed_metadata,
            model_routes=model_routes,
            safety_policy=safety_policy,
            safety_receipt=safety_receipt,
            model_armor=model_armor,
            agent_gateway=agent_gateway,
            max_attempts=max_attempts,
        )
        write_firestore(run_id, registry_payload)
    except Exception as exc:
        return {
            "enabled": True,
            "status": "not_promoted",
            "reason": "promotion_failed",
            "target_uri": f"{bucket_uri}/runs/{run_id}",
            "error": str(exc),
        }
    return {
        "enabled": True,
        "status": "promoted",
        "reason": "gcs_and_firestore_written",
        "target_uri": f"{bucket_uri}/runs/{run_id}",
        "artifact_paths": registry_payload,
    }


def _ready_without_write(*, env: Mapping[str, str], reason: str) -> dict[str, Any]:
    promotion = _promotion_decision(b_gate_passed=True, env=env)
    promotion["reason"] = reason
    return promotion


def _upload_existing_artifacts(
    *,
    run_id: str,
    artifact_paths: dict[str, str],
    bucket_uri: str,
    uploader: ArtifactUploader,
) -> dict[str, str]:
    uploaded: dict[str, str] = {}
    for key in (
        "input_path",
        "attempts_path",
        "checkpoint_path",
        "record_path",
        "cassette_path",
        "deterministic_eval_result_path",
    ):
        path_text = artifact_paths.get(key, "")
        if not path_text:
            continue
        source_path = Path(path_text)
        if not source_path.exists():
            continue
        target_uri = f"{bucket_uri}/runs/{run_id}/{source_path.name}"
        uploader(source_path, target_uri)
        uploaded[key] = target_uri
    return uploaded


def _build_firestore_registry_payload(
    *,
    run_id: str,
    uploaded_paths: dict[str, str],
    b_gate: dict[str, Any],
    seed_id: str | None,
    seed_metadata: Mapping[str, Any],
    model_routes: Mapping[str, str],
    safety_policy: Mapping[str, Any],
    safety_receipt: Mapping[str, Any],
    model_armor: Mapping[str, Any],
    agent_gateway: Mapping[str, Any],
    max_attempts: int | None,
) -> dict[str, Any]:
    payload = {
        **uploaded_paths,
        "run_id": run_id,
        "status": "completed",
        "seed_id": seed_id,
        "seed_metadata": dict(seed_metadata),
        "model_routes": dict(model_routes),
        "safety_policy": dict(safety_policy),
        "safety_receipt": dict(safety_receipt),
        "model_armor": dict(model_armor),
        "agent_gateway": dict(agent_gateway),
        "max_attempts": max_attempts,
        "b_gate_passed": b_gate.get("passed"),
        "promotion_status": "promoted",
        "promotion_reason": "gcs_and_firestore_written",
        "artifact_paths": dict(uploaded_paths),
    }
    selected_metrics = b_gate.get("selected_metrics") or {}
    verifier_parse_ok_rate = selected_metrics.get("verifier_parse_ok_rate")
    if verifier_parse_ok_rate is not None:
        payload["min_verifier_parse_ok_rate"] = float(verifier_parse_ok_rate)
    return payload


def _upload_gcs_artifact(source_path: Path, target_uri: str) -> None:
    import gcsfs

    filesystem = gcsfs.GCSFileSystem()
    with filesystem.open(target_uri, "wb") as target_file:
        target_file.write(source_path.read_bytes())


def _write_firestore_run_registry(run_id: str, payload: dict[str, Any]) -> None:
    from google.cloud import firestore

    client = firestore.Client(
        project=os.getenv(RUN_REGISTRY_FIRESTORE_PROJECT_ENV) or None,
        database=os.getenv(RUN_REGISTRY_FIRESTORE_DATABASE_ENV) or None,
    )
    collection = os.getenv(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    client.collection(collection).document(run_id).set(payload)


def _env_flag(
    name: str,
    *,
    environ: Mapping[str, str],
    default: bool = False,
) -> bool:
    value = environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

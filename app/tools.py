import json
import os
import sys
import tempfile
from collections import Counter
from collections.abc import Awaitable, Callable
from hashlib import sha256
from importlib import util as importlib_util
from pathlib import Path
from typing import Any

from app.run_registry import resolve_run_artifacts

BARRED_ROOT = Path(os.getenv("BARRED_ROOT", Path(__file__).resolve().parents[2])).resolve()
BARRED_DEBATE_RUNTIME_ROOT = Path(
    os.getenv("BARRED_DEBATE_RUNTIME_ROOT", Path(__file__).resolve().parents[1])
).resolve()
OFFLINE_B_GATE_PATH = BARRED_ROOT / "scenarios" / "debate" / "offline_b_gate.py"
RUN_REGISTRY_PATH = Path(
    os.getenv("BARRED_RUN_REGISTRY_PATH", BARRED_ROOT / "run_registry.json")
).resolve()
RUN_REGISTRY_URI = os.getenv("BARRED_RUN_REGISTRY_GCS_URI", "")
RUN_REGISTRY_FIRESTORE_COLLECTION = os.getenv("BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION", "")
RUN_REGISTRY_FIRESTORE_PROJECT = os.getenv("BARRED_RUN_REGISTRY_FIRESTORE_PROJECT", "")
RUN_REGISTRY_FIRESTORE_DATABASE = os.getenv("BARRED_RUN_REGISTRY_FIRESTORE_DATABASE", "")
GCS_ARTIFACT_CACHE_DIR = Path(
    os.getenv(
        "BARRED_GCS_ARTIFACT_CACHE_DIR",
        str(Path(tempfile.gettempdir()) / "barred-fleet-artifacts"),
    )
)
GCS_URI_PREFIX = "gs://"
DEFAULT_JUDGE_URL = "http://127.0.0.1:9009"
DEFAULT_PRO_DEBATER_URL = "http://127.0.0.1:9019/"
DEFAULT_CON_DEBATER_URL = "http://127.0.0.1:9018/"
DEMO_RUN_ARTIFACTS: dict[str, dict[str, str | float]] = {
    "pilot-v1-calibrated-pecan": {
        "input_path": "training_corpus_calibrated_pecan.jsonl",
        "attempts_path": "artifacts/attempts/pilot-v1-calibrated-pecan.jsonl",
        "deterministic_eval_result_path": (
            "barred-fleet/tests/fixtures/pecan_demo/deterministic_eval_result.json"
        ),
        "min_verifier_parse_ok_rate": 1.0,
    },
}


def _resolve_artifact_path(path_text: str, *, base_dir: Path = BARRED_ROOT) -> Path:
    if not path_text or not path_text.strip():
        raise ValueError("artifact path must be a non-empty string")
    if path_text.startswith(GCS_URI_PREFIX):
        return _materialize_gcs_artifact(path_text)

    path = Path(path_text)
    resolved = path.resolve() if path.is_absolute() else (base_dir / path).resolve()
    resolved.relative_to(base_dir.resolve())
    return resolved


def _materialize_gcs_artifact(uri: str) -> Path:
    if not uri.startswith(GCS_URI_PREFIX):
        raise ValueError(f"GCS artifact URI must use {GCS_URI_PREFIX}")

    import gcsfs

    cache_key = sha256(uri.encode("utf-8")).hexdigest()[:16]
    suffix = Path(uri.removeprefix(GCS_URI_PREFIX)).name or "artifact"
    local_path = GCS_ARTIFACT_CACHE_DIR / cache_key / suffix
    local_path.parent.mkdir(parents=True, exist_ok=True)

    filesystem = gcsfs.GCSFileSystem()
    with filesystem.open(uri, "rb") as source_file:
        local_path.write_bytes(source_file.read())
    return local_path


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as artifact_file:
        payload = json.load(artifact_file)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as artifact_file:
        for line_number, line in enumerate(artifact_file, 1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(payload)
    return rows


def _load_offline_b_gate_module() -> Any:
    module_name = "_barred_offline_b_gate"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib_util.spec_from_file_location(module_name, OFFLINE_B_GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load B-gate module from {OFFLINE_B_GATE_PATH}")

    module = importlib_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_barred_import_path() -> None:
    for path in reversed(
        (
            BARRED_DEBATE_RUNTIME_ROOT,
            BARRED_DEBATE_RUNTIME_ROOT / "src",
            BARRED_ROOT,
            BARRED_ROOT / "src",
        )
    ):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


def build_debate_case_payload(
    *,
    code: str,
    predicate: str,
    run_id: str = "barred-fleet-adhoc",
    seed: int = 42,
    mode: str = "record",
    target_verdict: str = "True",
    target_dimension: str = "Security Invariants",
    num_rounds: int = 2,
    max_refinements: int = 1,
    output_file: str = "training_corpus.jsonl",
    attempts_path: str = "",
    checkpoint_path: str = "",
    record_path: str = "",
    cassette_path: str = "",
    clock_now: str = "",
    resume: bool = False,
    pro_debater_url: str = DEFAULT_PRO_DEBATER_URL,
    con_debater_url: str = DEFAULT_CON_DEBATER_URL,
) -> dict[str, Any]:
    if not code.strip():
        raise ValueError("code must be a non-empty string")
    if not predicate.strip():
        raise ValueError("predicate must be a non-empty string")
    if mode not in {"record", "replay"}:
        raise ValueError("mode must be 'record' or 'replay'")

    resolved_checkpoint_path = checkpoint_path or f"artifacts/checkpoints/{run_id}/{seed}.json"
    resolved_record_path = record_path or f"artifacts/runs/{run_id}/{seed}.json"
    resolved_attempts_path = attempts_path or f"artifacts/attempts/{run_id}.jsonl"
    resolved_cassette_path = cassette_path or f"artifacts/cassettes/{run_id}.json"

    config: dict[str, Any] = {
        "run_id": run_id,
        "seed": seed,
        "mode": mode,
        "resume": resume,
        "checkpoint_path": resolved_checkpoint_path,
        "record_path": resolved_record_path,
        "attempts_path": resolved_attempts_path,
        "cassette_path": resolved_cassette_path,
        "topic": code,
        "predicate": predicate,
        "target_verdict": target_verdict,
        "target_dimension": target_dimension,
        "num_rounds": num_rounds,
        "max_refinements": max_refinements,
        "output_file": output_file,
    }
    if clock_now:
        config["clock_now"] = clock_now

    return {
        "participants": {
            "pro_debater": pro_debater_url,
            "con_debater": con_debater_url,
        },
        "config": config,
    }


async def execute_debate_case(
    *,
    payload: dict[str, Any],
    judge_url: str = DEFAULT_JUDGE_URL,
    sender: Callable[[str, str], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if sender is None:
        _ensure_barred_import_path()
        from agentbeats.client import send_message

        async def default_sender(message: str, base_url: str) -> dict[str, Any]:
            return await send_message(message, base_url)

        sender = default_sender

    result = await sender(json.dumps(payload), judge_url)
    config = payload["config"]
    return {
        "status": result.get("status", "completed"),
        "context_id": result.get("context_id"),
        "response_excerpt": str(result.get("response", ""))[:1000],
        "judge_url": judge_url,
        "artifact_paths": {
            "attempts_path": config.get("attempts_path"),
            "checkpoint_path": config.get("checkpoint_path"),
            "record_path": config.get("record_path"),
            "cassette_path": config.get("cassette_path"),
            "output_file": config.get("output_file"),
        },
        "payload_controls": {
            "run_id": config.get("run_id"),
            "seed": config.get("seed"),
            "mode": config.get("mode"),
            "resume": config.get("resume"),
            "num_rounds": config.get("num_rounds"),
            "max_refinements": config.get("max_refinements"),
        },
    }


def _summarize_attempts(path: Path) -> dict[str, Any]:
    rows = _load_jsonl(path)
    decisions = Counter(str(row.get("decision", "unknown")) for row in rows)
    pre_filter_stages = Counter(
        str(row.get("pre_filter_stage", "unknown"))
        for row in rows
        if row.get("pre_filter_stage") is not None
    )
    verifier_rows = [
        row.get("verifier")
        for row in rows
        if isinstance(row.get("verifier"), dict)
    ]
    verifier_called = sum(1 for verifier in verifier_rows if verifier.get("called"))
    verifier_passed = sum(1 for verifier in verifier_rows if verifier.get("passes_audit") is True)

    return {
        "path": str(path),
        "exists": True,
        "row_count": len(rows),
        "decisions": dict(sorted(decisions.items())),
        "pre_filter_stages": dict(sorted(pre_filter_stages.items())),
        "verifier": {
            "rows": len(verifier_rows),
            "called": verifier_called,
            "passes_audit": verifier_passed,
        },
    }


def _summarize_checkpoint(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "path": str(path),
        "exists": True,
        "schema_version": payload.get("schema_version"),
        "run_id": payload.get("run_id"),
        "seed": payload.get("seed"),
        "phase": payload.get("phase"),
        "refinement_round": payload.get("refinement_round"),
        "updated_at": payload.get("updated_at"),
    }


def _summarize_record(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    usage_events = payload.get("usage_events")
    return {
        "path": str(path),
        "exists": True,
        "run_id": payload.get("run_id"),
        "rng_seed": payload.get("rng_seed"),
        "created_at": payload.get("created_at"),
        "models": payload.get("models", {}),
        "usage_event_count": len(usage_events) if isinstance(usage_events, list) else 0,
    }


def _extract_attempt_models(path: Path) -> dict[str, Any]:
    rows = _load_jsonl(path)
    model_counts: Counter[str] = Counter()
    usage_models: Counter[str] = Counter()
    verifier_models: Counter[str] = Counter()

    for row in rows:
        verifier = row.get("verifier")
        if isinstance(verifier, dict) and verifier.get("model"):
            verifier_models[str(verifier["model"])] += 1

        llm_usage = row.get("llm_usage")
        by_model = llm_usage.get("by_model") if isinstance(llm_usage, dict) else None
        if isinstance(by_model, dict):
            for model_name, model_usage in by_model.items():
                calls = 1
                if isinstance(model_usage, dict):
                    calls = int(model_usage.get("calls") or 0)
                usage_models[str(model_name)] += calls
                model_counts[str(model_name)] += calls

    return {
        "attempt_rows": len(rows),
        "by_model_calls": dict(sorted(model_counts.items())),
        "usage_by_model_calls": dict(sorted(usage_models.items())),
        "verifier_model_counts": dict(sorted(verifier_models.items())),
    }


def _extract_model_routing(
    *,
    record_path: str = "",
    attempts_path: str = "",
    base_dir: Path = BARRED_ROOT,
) -> dict[str, Any]:
    routing: dict[str, Any] = {
        "record_models": {},
        "attempt_models": {},
    }
    if record_path:
        record_file = _resolve_artifact_path(record_path, base_dir=base_dir)
        if record_file.exists():
            routing["record_models"] = _summarize_record(record_file).get("models", {})
    if attempts_path:
        attempts_file = _resolve_artifact_path(attempts_path, base_dir=base_dir)
        if attempts_file.exists():
            routing["attempt_models"] = _extract_attempt_models(attempts_file)
    return routing


def _summarize_cassette(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "path": str(path),
        "exists": True,
        "entry_count": len(payload),
    }


def _missing_artifact(path_text: str, *, base_dir: Path) -> dict[str, Any]:
    path = _resolve_artifact_path(path_text, base_dir=base_dir)
    return {
        "path": str(path),
        "exists": False,
    }


def build_artifact_summary(
    *,
    attempts_path: str = "",
    checkpoint_path: str = "",
    record_path: str = "",
    cassette_path: str = "",
    base_dir: Path = BARRED_ROOT,
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}

    for key, path_text, summarizer in (
        ("attempts", attempts_path, _summarize_attempts),
        ("checkpoint", checkpoint_path, _summarize_checkpoint),
        ("record", record_path, _summarize_record),
        ("cassette", cassette_path, _summarize_cassette),
    ):
        if not path_text:
            continue
        path = _resolve_artifact_path(path_text, base_dir=base_dir)
        artifacts[key] = summarizer(path) if path.exists() else _missing_artifact(path_text, base_dir=base_dir)

    return {
        "status": "ok",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "notes": [
            "Summary is computed from deterministic artifact files only.",
            "Cassette entries are local replay records, not provider-side cache telemetry.",
        ],
    }


def _failed_b_gate_checks(metrics: dict[str, Any]) -> list[str]:
    failed = [
        check_name
        for check_name, passed in sorted((metrics.get("checks") or {}).items())
        if passed is False
    ]
    if metrics.get("anti_gaming_valid") is False:
        failed.append("anti_gaming_valid")
    if metrics.get("failures"):
        failed.append("row_failures")
    return failed


def build_b_gate_result(
    *,
    input_path: str,
    attempts_path: str = "",
    max_unsupported_rate: float = 0.05,
    max_inconclusive_rate: float = 0.20,
    min_anchor_match_rate: float = 0.80,
    min_verifier_pass_rate: float = 0.0,
    min_verifier_parse_ok_rate: float = 0.0,
    max_accepted_logic_error_rate: float = 0.0,
    base_dir: Path = BARRED_ROOT,
) -> dict[str, Any]:
    input_file = _resolve_artifact_path(input_path, base_dir=base_dir)
    attempts_file = _resolve_artifact_path(attempts_path, base_dir=base_dir) if attempts_path else None

    if not input_file.exists():
        return {
            "status": "error",
            "passed": False,
            "error": f"input_path does not exist: {input_file}",
        }
    if attempts_file is not None and not attempts_file.exists():
        return {
            "status": "error",
            "passed": False,
            "error": f"attempts_path does not exist: {attempts_file}",
        }

    offline_b_gate = _load_offline_b_gate_module()
    config = offline_b_gate.BGateConfig(
        thresholds=offline_b_gate.BGateThresholds(
            max_unsupported_in_accepted_rate=max_unsupported_rate,
            max_inconclusive_in_accepted_rate=max_inconclusive_rate,
            min_anchor_match_rate=min_anchor_match_rate,
            min_verifier_pass_rate=min_verifier_pass_rate,
            min_verifier_parse_ok_rate=min_verifier_parse_ok_rate,
            max_accepted_logic_error_rate=max_accepted_logic_error_rate,
        )
    )
    metrics = offline_b_gate.compute_b_metrics(
        input_path=str(input_file),
        attempts_path=str(attempts_file) if attempts_file else None,
        config=config,
    )
    failed_checks = _failed_b_gate_checks(metrics)

    return {
        "status": "ok",
        "passed": bool(metrics.get("pass")),
        "failed_checks": failed_checks,
        "selected_metrics": {
            "total_rows": metrics.get("total_rows"),
            "accepted_rows": metrics.get("accepted_rows"),
            "b0_structural_completeness_pass_rate": metrics.get("b0_structural_completeness_pass_rate"),
            "b1_unsupported_in_accepted_rate": metrics.get("b1_unsupported_in_accepted_rate"),
            "b1_inconclusive_in_accepted_rate": metrics.get("b1_inconclusive_in_accepted_rate"),
            "b2_anchor_match_rate": metrics.get("b2_anchor_match_rate"),
            "verifier_parse_ok_rate": metrics.get("verifier_parse_ok_rate"),
            "verifier_pass_rate": metrics.get("verifier_pass_rate"),
            "accepted_attempt_logic_error_rate": metrics.get("accepted_attempt_logic_error_rate"),
            "accepted_corpus_logic_error_rate": metrics.get("accepted_corpus_logic_error_rate"),
        },
        "metrics": metrics,
    }


def _summarize_eval_result(path_text: str, *, base_dir: Path = BARRED_ROOT) -> dict[str, Any]:
    path = _resolve_artifact_path(path_text, base_dir=base_dir)
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
        }

    payload = _load_json(path)
    return {
        "path": str(path),
        "exists": True,
        "summary_metrics": payload.get("summary_metrics", []),
    }


def build_observability_report(
    *,
    run_id: str,
    input_path: str,
    attempts_path: str = "",
    checkpoint_path: str = "",
    record_path: str = "",
    cassette_path: str = "",
    llm_eval_result_path: str = "",
    deterministic_eval_result_path: str = "",
    min_verifier_parse_ok_rate: float = 0.0,
    base_dir: Path = BARRED_ROOT,
) -> dict[str, Any]:
    artifact_summary = build_artifact_summary(
        attempts_path=attempts_path,
        checkpoint_path=checkpoint_path,
        record_path=record_path,
        cassette_path=cassette_path,
        base_dir=base_dir,
    )
    b_gate = build_b_gate_result(
        input_path=input_path,
        attempts_path=attempts_path,
        min_verifier_parse_ok_rate=min_verifier_parse_ok_rate,
        base_dir=base_dir,
    )
    eval_results = {
        "llm": (
            _summarize_eval_result(llm_eval_result_path, base_dir=base_dir)
            if llm_eval_result_path
            else None
        ),
        "deterministic": (
            _summarize_eval_result(deterministic_eval_result_path, base_dir=base_dir)
            if deterministic_eval_result_path
            else None
        ),
    }
    selected_metrics = b_gate.get("selected_metrics") if b_gate.get("status") == "ok" else {}
    report_checks = {
        "artifacts_read": artifact_summary["artifact_count"] > 0,
        "b_gate_passed": b_gate.get("passed") is True,
        "verifier_parse_ok_rate_met": (
            (selected_metrics or {}).get("verifier_parse_ok_rate") is None
            or (selected_metrics or {}).get("verifier_parse_ok_rate") >= min_verifier_parse_ok_rate
        ),
        "deterministic_eval_present": bool(
            eval_results["deterministic"] and eval_results["deterministic"].get("exists")
        ),
    }

    return {
        "status": "ok" if all(report_checks.values()) else "attention_required",
        "run_id": run_id,
        "artifact_paths": {
            "input_path": input_path,
            "attempts_path": attempts_path,
            "checkpoint_path": checkpoint_path,
            "record_path": record_path,
            "cassette_path": cassette_path,
            "llm_eval_result_path": llm_eval_result_path,
            "deterministic_eval_result_path": deterministic_eval_result_path,
        },
        "artifact_registry": build_artifact_registry(
            {
                "input_path": input_path,
                "attempts_path": attempts_path,
                "checkpoint_path": checkpoint_path,
                "record_path": record_path,
                "cassette_path": cassette_path,
                "llm_eval_result_path": llm_eval_result_path,
                "deterministic_eval_result_path": deterministic_eval_result_path,
            }
        ),
        "artifact_summary": artifact_summary,
        "b_gate": {
            "status": b_gate.get("status"),
            "passed": b_gate.get("passed"),
            "failed_checks": b_gate.get("failed_checks", []),
            "selected_metrics": selected_metrics,
            "error": b_gate.get("error"),
        },
        "model_routing": _extract_model_routing(
            record_path=record_path,
            attempts_path=attempts_path,
            base_dir=base_dir,
        ),
        "eval_results": eval_results,
        "report_checks": report_checks,
        "notes": [
            "Report is computed from local artifacts and eval result files only.",
            "Cassette replay records are not provider-side cache telemetry.",
        ],
    }


def build_artifact_registry(
    artifact_paths: dict[str, Any],
    *,
    diagnostic_receipt_path: str = "",
) -> dict[str, dict[str, Any]]:
    registry = {
        "corpus": _artifact_registry_entry(artifact_paths.get("input_path")),
        "attempts": _artifact_registry_entry(artifact_paths.get("attempts_path")),
        "checkpoint": _artifact_registry_entry(artifact_paths.get("checkpoint_path")),
        "record": _artifact_registry_entry(artifact_paths.get("record_path")),
        "cassette": _artifact_registry_entry(artifact_paths.get("cassette_path")),
        "llm_eval_result": _artifact_registry_entry(
            artifact_paths.get("llm_eval_result_path")
        ),
        "deterministic_eval_result": _artifact_registry_entry(
            artifact_paths.get("deterministic_eval_result_path")
        ),
        "diagnostic_receipt": _artifact_registry_entry(diagnostic_receipt_path),
    }
    return registry


def _artifact_registry_entry(path: Any) -> dict[str, Any]:
    path_text = str(path or "")
    return {
        "path": path_text,
        "available": bool(path_text),
        "storage": _artifact_storage_label(path_text),
    }


def _artifact_storage_label(path_text: str) -> str:
    if path_text.startswith("gs://"):
        return "gcs"
    if path_text:
        return "local"
    return "missing"


def _apply_demo_run_defaults(
    *,
    run_id: str,
    input_path: str,
    attempts_path: str,
    checkpoint_path: str,
    record_path: str,
    cassette_path: str,
    llm_eval_result_path: str,
    deterministic_eval_result_path: str,
    min_verifier_parse_ok_rate: float,
) -> dict[str, Any]:
    defaults = resolve_run_artifacts(
        run_id,
        registry_path=RUN_REGISTRY_PATH,
        registry_uri=RUN_REGISTRY_URI,
        firestore_collection=RUN_REGISTRY_FIRESTORE_COLLECTION,
        firestore_project=RUN_REGISTRY_FIRESTORE_PROJECT,
        firestore_database=RUN_REGISTRY_FIRESTORE_DATABASE,
    )
    if not defaults:
        defaults = DEMO_RUN_ARTIFACTS.get(run_id, {})
    return {
        "input_path": input_path or str(defaults.get("input_path", "")),
        "attempts_path": attempts_path or str(defaults.get("attempts_path", "")),
        "checkpoint_path": checkpoint_path or str(defaults.get("checkpoint_path", "")),
        "record_path": record_path or str(defaults.get("record_path", "")),
        "cassette_path": cassette_path or str(defaults.get("cassette_path", "")),
        "llm_eval_result_path": llm_eval_result_path
        or str(defaults.get("llm_eval_result_path", "")),
        "deterministic_eval_result_path": deterministic_eval_result_path
        or str(defaults.get("deterministic_eval_result_path", "")),
        "min_verifier_parse_ok_rate": (
            min_verifier_parse_ok_rate
            if min_verifier_parse_ok_rate
            else float(defaults.get("min_verifier_parse_ok_rate", 0.0))
        ),
    }


def run_b_gate(
    input_path: str,
    attempts_path: str = "",
    max_unsupported_rate: float = 0.05,
    max_inconclusive_rate: float = 0.20,
    min_anchor_match_rate: float = 0.80,
    min_verifier_pass_rate: float = 0.0,
    min_verifier_parse_ok_rate: float = 0.0,
    max_accepted_logic_error_rate: float = 0.0,
) -> dict[str, Any]:
    """Run BARRED offline B-gate metrics over corpus and attempt artifacts.

    Args:
        input_path: Path to the training corpus JSONL artifact, relative to the BARRED repo root.
        attempts_path: Optional path to attempts JSONL, relative to the BARRED repo root.
        max_unsupported_rate: Maximum allowed unsupported predicate rate.
        max_inconclusive_rate: Maximum allowed inconclusive predicate rate.
        min_anchor_match_rate: Minimum required anchor match rate.
        min_verifier_pass_rate: Minimum required verifier pass rate when attempts are supplied.
        min_verifier_parse_ok_rate: Minimum required verifier parse-ok rate when attempts are supplied.
        max_accepted_logic_error_rate: Maximum allowed accepted logic-error rate.

    Returns:
        B-gate pass/fail status, failed checks, selected metrics, and full metrics.
    """
    return build_b_gate_result(
        input_path=input_path,
        attempts_path=attempts_path,
        max_unsupported_rate=max_unsupported_rate,
        max_inconclusive_rate=max_inconclusive_rate,
        min_anchor_match_rate=min_anchor_match_rate,
        min_verifier_pass_rate=min_verifier_pass_rate,
        min_verifier_parse_ok_rate=min_verifier_parse_ok_rate,
        max_accepted_logic_error_rate=max_accepted_logic_error_rate,
    )


async def run_debate_case(
    code: str,
    predicate: str,
    run_id: str = "barred-fleet-adhoc",
    seed: int = 42,
    mode: str = "record",
    judge_url: str = DEFAULT_JUDGE_URL,
    target_verdict: str = "True",
    target_dimension: str = "Security Invariants",
    num_rounds: int = 2,
    max_refinements: int = 1,
    output_file: str = "training_corpus.jsonl",
    attempts_path: str = "",
    checkpoint_path: str = "",
    record_path: str = "",
    cassette_path: str = "",
    clock_now: str = "",
    resume: bool = False,
) -> dict[str, Any]:
    """Run one BARRED debate case through the existing local A2A judge.

    The BARRED debate stack must already be running, for example with
    `uv run agentbeats-run scenarios/debate/barred_test.toml --serve-only`.

    Args:
        code: Candidate code snippet or patch to debate.
        predicate: Specific vulnerability claim to evaluate.
        run_id: Stable run identifier for artifacts.
        seed: Deterministic seed passed through to BARRED.
        mode: BARRED cassette mode, either record or replay.
        judge_url: Existing BARRED judge A2A endpoint.
        target_verdict: Target verdict expected by BARRED generation.
        target_dimension: Evaluation dimension metadata.
        num_rounds: Number of pro/con debate rounds.
        max_refinements: Maximum BARRED refinement rounds.
        output_file: Existing BARRED accepted-corpus output path.
        attempts_path: Existing BARRED attempts JSONL path.
        checkpoint_path: Existing BARRED checkpoint path.
        record_path: Existing BARRED run-record path.
        cassette_path: Existing BARRED cassette path.
        clock_now: Optional fixed timestamp for deterministic records.
        resume: Whether the existing judge should resume from checkpoint.

    Returns:
        Status, response excerpt, context id, artifact paths, and payload controls.
    """
    payload = build_debate_case_payload(
        code=code,
        predicate=predicate,
        run_id=run_id,
        seed=seed,
        mode=mode,
        target_verdict=target_verdict,
        target_dimension=target_dimension,
        num_rounds=num_rounds,
        max_refinements=max_refinements,
        output_file=output_file,
        attempts_path=attempts_path,
        checkpoint_path=checkpoint_path,
        record_path=record_path,
        cassette_path=cassette_path,
        clock_now=clock_now,
        resume=resume,
    )
    return await execute_debate_case(payload=payload, judge_url=judge_url)


def report_barred_run(
    run_id: str,
    input_path: str = "",
    attempts_path: str = "",
    checkpoint_path: str = "",
    record_path: str = "",
    cassette_path: str = "",
    llm_eval_result_path: str = "",
    deterministic_eval_result_path: str = "",
    min_verifier_parse_ok_rate: float = 0.0,
) -> dict[str, Any]:
    """Build a deterministic BARRED-Fleet observability report.

    Args:
        run_id: Human-readable run identifier to attach to the report.
        input_path: Path to the accepted corpus JSONL artifact, relative to the BARRED repo root.
        attempts_path: Optional path to attempts JSONL, relative to the BARRED repo root.
        checkpoint_path: Optional path to checkpoint JSON, relative to the BARRED repo root.
        record_path: Optional path to run-record JSON, relative to the BARRED repo root.
        cassette_path: Optional path to cassette JSON, relative to the BARRED repo root.
        llm_eval_result_path: Optional path to an LLM-backed eval result JSON.
        deterministic_eval_result_path: Optional path to a deterministic eval result JSON.
        min_verifier_parse_ok_rate: Minimum verifier parse-ok rate expected by this report.

    Returns:
        A local, deterministic report containing artifact status, B-gate status,
        model routing, verifier metrics, eval result summaries, and report checks.
    """
    resolved_paths = _apply_demo_run_defaults(
        run_id=run_id,
        input_path=input_path,
        attempts_path=attempts_path,
        checkpoint_path=checkpoint_path,
        record_path=record_path,
        cassette_path=cassette_path,
        llm_eval_result_path=llm_eval_result_path,
        deterministic_eval_result_path=deterministic_eval_result_path,
        min_verifier_parse_ok_rate=min_verifier_parse_ok_rate,
    )
    if not resolved_paths["input_path"]:
        artifact_registry = build_artifact_registry(resolved_paths)
        return {
            "status": "attention_required",
            "run_id": run_id,
            "artifact_paths": resolved_paths,
            "artifact_registry": artifact_registry,
            "artifact_summary": {
                "status": "ok",
                "artifact_count": 0,
                "artifacts": {},
                "notes": [
                    "Summary is computed from deterministic artifact files only.",
                    "Cassette entries are local replay records, not provider-side cache telemetry.",
                ],
            },
            "b_gate": {
                "status": "error",
                "passed": False,
                "failed_checks": [],
                "selected_metrics": {},
                "error": (
                    "input_path is required unless run_id has a registered run or known demo fixture."
                ),
            },
            "model_routing": {"record_models": {}, "attempt_models": {}},
            "eval_results": {"llm": None, "deterministic": None},
            "report_checks": {
                "artifacts_read": False,
                "b_gate_passed": False,
                "verifier_parse_ok_rate_met": False,
                "deterministic_eval_present": False,
            },
            "notes": [
                "Report is computed from local artifacts and eval result files only.",
                "Cassette replay records are not provider-side cache telemetry.",
            ],
        }
    return build_observability_report(
        run_id=run_id,
        input_path=resolved_paths["input_path"],
        attempts_path=resolved_paths["attempts_path"],
        checkpoint_path=resolved_paths["checkpoint_path"],
        record_path=resolved_paths["record_path"],
        cassette_path=resolved_paths["cassette_path"],
        llm_eval_result_path=resolved_paths["llm_eval_result_path"],
        deterministic_eval_result_path=resolved_paths["deterministic_eval_result_path"],
        min_verifier_parse_ok_rate=resolved_paths["min_verifier_parse_ok_rate"],
    )


def summarize_artifacts(
    attempts_path: str = "",
    checkpoint_path: str = "",
    record_path: str = "",
    cassette_path: str = "",
) -> dict[str, Any]:
    """Summarize BARRED run artifacts without calling a model.

    Args:
        attempts_path: Path to an attempts JSONL artifact, relative to the BARRED repo root.
        checkpoint_path: Path to a checkpoint JSON artifact, relative to the BARRED repo root.
        record_path: Path to a run-record JSON artifact, relative to the BARRED repo root.
        cassette_path: Path to a cassette JSON artifact, relative to the BARRED repo root.

    Returns:
        A deterministic summary of artifact existence, counts, decisions, and verifier metadata.
    """
    return build_artifact_summary(
        attempts_path=attempts_path,
        checkpoint_path=checkpoint_path,
        record_path=record_path,
        cassette_path=cassette_path,
    )


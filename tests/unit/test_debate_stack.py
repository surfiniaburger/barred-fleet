from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.debate_stack import (
    DebateStackConfig,
    DebateStackStartupError,
    build_debate_stack_command,
    build_debate_stack_env,
    should_start_internal_debate_stack,
    start_internal_debate_stack,
)


class FakeProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        return self.returncode or 0


def test_should_start_internal_stack_is_opt_in() -> None:
    assert should_start_internal_debate_stack({}) is False
    assert should_start_internal_debate_stack({"BARRED_START_INTERNAL_DEBATE_STACK": "false"}) is False
    assert should_start_internal_debate_stack({"BARRED_START_INTERNAL_DEBATE_STACK": "true"}) is True


def test_build_debate_stack_command_targets_packaged_runtime(tmp_path: Path) -> None:
    config = DebateStackConfig(runtime_root=tmp_path)

    command = build_debate_stack_command(config)

    assert command == [
        sys.executable,
        str(tmp_path / "src" / "agentbeats" / "run_scenario.py"),
        str(tmp_path / "scenarios" / "debate" / "barred_test.toml"),
        "--serve-only",
    ]


def test_packaged_runtime_files_are_present() -> None:
    runtime_root = Path(__file__).resolve().parents[2]

    assert (runtime_root / "src" / "agentbeats" / "run_scenario.py").is_file()
    assert (runtime_root / "src" / "agentbeats" / "client.py").is_file()
    assert (runtime_root / "scenarios" / "debate" / "barred_test.toml").is_file()
    assert (runtime_root / "scenarios" / "debate" / "adk_debate_judge.py").is_file()
    assert (runtime_root / "scenarios" / "debate" / "adk_debate_verifier.py").is_file()
    assert (runtime_root / "scenarios" / "debate" / "debater.py").is_file()
    assert (runtime_root / "scenarios" / "debate" / "cve_seeds_test.jsonl").is_file()


def test_build_debate_stack_env_passes_model_routes(tmp_path: Path) -> None:
    config = DebateStackConfig(
        runtime_root=tmp_path,
        model_routes={
            "generator": "generator-model",
            "judge": "judge-model",
            "verifier": "verifier-model",
        },
    )

    env = build_debate_stack_env(config, base_env={"PATH": "/bin"})

    assert env["JUDGE_MODEL"] == "judge-model"
    assert env["DEBATER_MODEL"] == "generator-model"
    assert env["GENERATOR_MODEL"] == "generator-model"
    assert env["VERIFIER_MODEL"] == "verifier-model"
    assert env["PYTHONPATH"].split(":")[:2] == [
        str(tmp_path / "src"),
        str(tmp_path),
    ]


def test_build_debate_stack_env_sets_vertex_context_for_gemini(tmp_path: Path) -> None:
    config = DebateStackConfig(runtime_root=tmp_path)

    env = build_debate_stack_env(
        config,
        base_env={
            "PATH": "/bin",
            "GOOGLE_CLOUD_PROJECT": "gem-creation",
            "GOOGLE_CLOUD_LOCATION": "global",
        },
    )

    assert env["JUDGE_MODEL"] == "vertex_ai/gemini-3.6-flash"
    assert env["DEBATER_MODEL"] == "vertex_ai/gemini-3.5-flash-lite"
    assert env["GENERATOR_MODEL"] == "vertex_ai/gemini-3.5-flash-lite"
    assert env["VERIFIER_MODEL"] == "vertex_ai/gemini-3.6-flash"
    assert env["VERTEXAI_PROJECT"] == "gem-creation"
    assert env["VERTEXAI_LOCATION"] == "global"
    assert env["LLM_SAMPLING_PROFILE"] == "vertex_gemini"


def test_start_internal_stack_returns_judge_url_and_cleans_up(tmp_path: Path) -> None:
    started: list[dict] = []
    process = FakeProcess()

    def fake_process_factory(command, **kwargs):
        started.append({"command": command, "kwargs": kwargs})
        return process

    def ready(_judge_url: str, _timeout_seconds: int) -> bool:
        return True

    config = DebateStackConfig(runtime_root=tmp_path, judge_url="http://127.0.0.1:9009")

    with start_internal_debate_stack(
        config,
        process_factory=fake_process_factory,
        readiness_probe=ready,
    ) as stack:
        assert stack.started is True
        assert stack.judge_url == "http://127.0.0.1:9009"
        assert started[0]["kwargs"]["cwd"] == str(tmp_path)

    assert process.terminated is True
    assert process.wait_calls == 1


def test_start_internal_stack_timeout_kills_process(tmp_path: Path) -> None:
    process = FakeProcess()

    def fake_process_factory(_command, **_kwargs):
        return process

    def never_ready(_judge_url: str, _timeout_seconds: int) -> bool:
        return False

    with pytest.raises(DebateStackStartupError, match="did not become ready"):
        with start_internal_debate_stack(
            DebateStackConfig(runtime_root=tmp_path, startup_timeout_seconds=1),
            process_factory=fake_process_factory,
            readiness_probe=never_ready,
        ):
            pass

    assert process.terminated is True
    assert process.wait_calls == 1

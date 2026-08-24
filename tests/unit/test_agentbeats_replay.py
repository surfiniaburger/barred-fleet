from __future__ import annotations

import sys
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from agentbeats.replay import LLMCassette, ReplayManager, RunRecord


def _manager(tmp_path: Path) -> ReplayManager:
    return ReplayManager(
        RunRecord(
            run_id="test-run",
            rng_seed=42,
            models={},
            generation_config={
                "default": {
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "top_k": 40,
                    "max_tokens": 128,
                }
            },
            created_at="2026-08-18T00:00:00Z",
        ),
        LLMCassette(str(tmp_path / "cassette.json"), mode="record"),
    )


def test_normalize_provider_kwargs_strips_ollama_options_for_gemini(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    kwargs = {"options": {"keep_alive": "24h"}, "timeout": 1200}

    manager._normalize_provider_kwargs("vertex_ai/gemini-3.6-flash", kwargs)

    assert kwargs == {"timeout": 1200}


def test_apply_generation_config_removes_deprecated_sampling_for_gemini_3(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    kwargs = {"options": {"keep_alive": "24h"}}

    manager._apply_generation_config("vertex_ai/gemini-3.6-flash", kwargs)

    assert kwargs == {"max_tokens": 128}


def test_apply_generation_config_preserves_ollama_sampling(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    kwargs = {"options": {"keep_alive": "24h"}}

    manager._apply_generation_config("ollama/gemma4:31b-cloud", kwargs)

    assert kwargs == {
        "temperature": 0.2,
        "top_p": 0.9,
        "top_k": 40,
        "max_tokens": 128,
        "options": {"keep_alive": "24h"},
    }

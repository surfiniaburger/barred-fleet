from __future__ import annotations

import sys
from pathlib import Path

RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from agentbeats.client import create_send_request


def test_create_send_request_includes_required_configuration() -> None:
    request = create_send_request(text="hello", context_id="ctx-1")

    assert request.HasField("message")
    assert request.HasField("configuration")
    assert request.message.context_id == "ctx-1"
    assert request.message.parts[0].text == "hello"

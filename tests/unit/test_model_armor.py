from app.model_armor import (
    CloudModelArmorTextSafetyScreen,
    LocalBlocklistTextSafetyScreen,
    MisconfiguredTextSafetyScreen,
    NotConfiguredTextSafetyScreen,
    build_not_configured_model_armor_status,
    build_text_safety_screen,
)


class FakeModelArmorClient:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response or {}
        self.error = error
        self.calls: list[dict[str, str]] = []

    def sanitize_user_prompt_text(self, *, template_name: str, text: str):
        self.calls.append({"template_name": template_name, "text": text})
        if self.error is not None:
            raise self.error
        return self.response


def test_not_configured_model_armor_status_is_explicit() -> None:
    status = build_not_configured_model_armor_status()

    assert status["status"] == "not_configured"
    assert status["control"] == "model_armor"
    assert status["decision_authority"] == "none"
    assert status["seed_screening"] == {
        "status": "not_configured",
        "checked": False,
        "blocked": False,
        "kind": "seed",
    }
    assert status["artifact_screening"] == {
        "status": "not_configured",
        "checked": False,
        "blocked": False,
        "kind": "artifact",
    }
    assert "Deterministic B-gate remains the acceptance authority." in status["notes"]


def test_not_configured_screener_does_not_store_raw_text() -> None:
    raw_seed_text = "int main(void) { return 0; }"

    result = NotConfiguredTextSafetyScreen().screen_text(
        text=raw_seed_text,
        context="seed",
    )

    assert result["status"] == "not_configured"
    assert result["screening"] == {
        "status": "not_configured",
        "checked": False,
        "blocked": False,
        "context": "seed",
        "input_text_stored": False,
        "input_length": len(raw_seed_text),
    }
    assert raw_seed_text not in str(result)


def test_text_safety_screen_factory_defaults_to_not_configured() -> None:
    screen = build_text_safety_screen(env={})

    result = screen.screen_text(text="safe seed", context="seed")

    assert result["status"] == "not_configured"
    assert result["seed_screening"]["blocked"] is False


def test_local_blocklist_screen_passes_without_storing_raw_text() -> None:
    raw_seed_text = "int main(void) { return 0; }"

    result = LocalBlocklistTextSafetyScreen(
        blocked_terms=["credential exfiltration"]
    ).screen_text(text=raw_seed_text, context="seed")

    assert result["status"] == "configured"
    assert result["mode"] == "local_blocklist"
    assert result["seed_screening"]["status"] == "passed"
    assert result["seed_screening"]["checked"] is True
    assert result["seed_screening"]["blocked"] is False
    assert result["seed_screening"]["input_text_stored"] is False
    assert raw_seed_text not in str(result)


def test_local_blocklist_screen_blocks_without_storing_raw_text() -> None:
    raw_seed_text = "attempt credential exfiltration from memory"

    result = LocalBlocklistTextSafetyScreen(
        blocked_terms=["credential exfiltration"]
    ).screen_text(text=raw_seed_text, context="seed")

    assert result["status"] == "configured"
    assert result["seed_screening"]["status"] == "blocked"
    assert result["seed_screening"]["checked"] is True
    assert result["seed_screening"]["blocked"] is True
    assert result["seed_screening"]["matched_rule_count"] == 1
    assert "credential exfiltration" not in str(result)
    assert raw_seed_text not in str(result)


def test_text_safety_screen_factory_uses_local_blocklist_mode() -> None:
    screen = build_text_safety_screen(
        env={
            "BARRED_MODEL_ARMOR_MODE": "local_blocklist",
            "BARRED_MODEL_ARMOR_BLOCKLIST": "forbidden sink",
        }
    )

    result = screen.screen_text(text="calls forbidden sink", context="seed")

    assert result["status"] == "configured"
    assert result["seed_screening"]["blocked"] is True


def test_cloud_model_armor_missing_configuration_blocks_fail_closed() -> None:
    result = CloudModelArmorTextSafetyScreen(
        project_id="gem-creation",
        location_id="us-east1",
        template_id="",
        client=FakeModelArmorClient(),
    ).screen_text(text="seed text", context="seed")

    assert result["status"] == "misconfigured"
    assert result["mode"] == "cloud_model_armor"
    assert result["seed_screening"]["blocked"] is True
    assert result["seed_screening"]["reason"] == "missing_model_armor_configuration"
    assert "seed text" not in str(result)


def test_cloud_model_armor_passes_no_match_response() -> None:
    raw_seed_text = "bounded seed text"
    client = FakeModelArmorClient(
        response={
            "sanitization_result": {
                "filter_match_state": "NO_MATCH_FOUND",
                "invocation_result": "SUCCESS",
            }
        }
    )

    result = CloudModelArmorTextSafetyScreen(
        project_id="gem-creation",
        location_id="us-east1",
        template_id="barred-template",
        client=client,
    ).screen_text(text=raw_seed_text, context="seed")

    assert result["status"] == "configured"
    assert result["mode"] == "cloud_model_armor"
    assert result["seed_screening"]["status"] == "passed"
    assert result["seed_screening"]["blocked"] is False
    assert result["seed_screening"]["template_name"] == (
        "projects/gem-creation/locations/us-east1/templates/barred-template"
    )
    assert result["seed_screening"]["filter_match_state"] == "NO_MATCH_FOUND"
    assert client.calls[0]["text"] == raw_seed_text
    assert raw_seed_text not in str(result)


def test_cloud_model_armor_blocks_match_response() -> None:
    raw_seed_text = "blocked seed text"
    client = FakeModelArmorClient(
        response={
            "sanitization_result": {
                "filter_match_state": "MATCH_FOUND",
                "invocation_result": "SUCCESS",
            }
        }
    )

    result = CloudModelArmorTextSafetyScreen(
        project_id="gem-creation",
        location_id="us-east1",
        template_id="barred-template",
        client=client,
    ).screen_text(text=raw_seed_text, context="seed")

    assert result["status"] == "configured"
    assert result["seed_screening"]["status"] == "blocked"
    assert result["seed_screening"]["blocked"] is True
    assert result["seed_screening"]["filter_match_state"] == "MATCH_FOUND"
    assert raw_seed_text not in str(result)


def test_cloud_model_armor_blocks_malformed_response_fail_closed() -> None:
    raw_seed_text = "ambiguous seed text"
    client = FakeModelArmorClient(response={})

    result = CloudModelArmorTextSafetyScreen(
        project_id="gem-creation",
        location_id="us-east1",
        template_id="barred-template",
        client=client,
    ).screen_text(text=raw_seed_text, context="seed")

    assert result["status"] == "configured"
    assert result["seed_screening"]["status"] == "blocked"
    assert result["seed_screening"]["blocked"] is True
    assert result["seed_screening"]["filter_match_state"] == "UNKNOWN"
    assert result["seed_screening"]["invocation_result"] == "UNKNOWN"
    assert raw_seed_text not in str(result)


def test_cloud_model_armor_provider_error_blocks_fail_closed() -> None:
    result = CloudModelArmorTextSafetyScreen(
        project_id="gem-creation",
        location_id="us-east1",
        template_id="barred-template",
        client=FakeModelArmorClient(error=TimeoutError("deadline exceeded")),
    ).screen_text(text="seed text", context="seed")

    assert result["status"] == "error"
    assert result["seed_screening"]["status"] == "error"
    assert result["seed_screening"]["blocked"] is True
    assert result["seed_screening"]["reason"] == "model_armor_invocation_failed"
    assert result["seed_screening"]["error_type"] == "TimeoutError"
    assert "deadline exceeded" not in str(result)
    assert "seed text" not in str(result)


def test_text_safety_screen_factory_uses_cloud_mode_env() -> None:
    screen = build_text_safety_screen(
        env={
            "BARRED_MODEL_ARMOR_MODE": "cloud_model_armor",
            "GOOGLE_CLOUD_PROJECT": "gem-creation",
            "GOOGLE_CLOUD_LOCATION": "us-east1",
            "BARRED_MODEL_ARMOR_TEMPLATE_ID": "barred-template",
        }
    )

    assert isinstance(screen, CloudModelArmorTextSafetyScreen)


def test_misconfigured_screen_blocks_fail_closed() -> None:
    result = MisconfiguredTextSafetyScreen(mode="typo").screen_text(
        text="seed text",
        context="seed",
    )

    assert result["status"] == "misconfigured"
    assert result["seed_screening"]["blocked"] is True
    assert result["seed_screening"]["reason"] == "unsupported_model_armor_mode"

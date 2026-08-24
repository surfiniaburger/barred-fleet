from app.agent_gateway import (
    CloudAgentGateway,
    LocalPolicyAgentGateway,
    build_agent_gateway,
    build_not_configured_agent_gateway_status,
)


class FakeCloudGatewayClient:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests = []

    def get_agent_gateway(self, *, gateway_resource: str):
        self.requests.append(gateway_resource)
        if self.error:
            raise self.error
        return self.response


def test_not_configured_gateway_reports_non_blocking_placeholder() -> None:
    gateway = build_agent_gateway(env={})

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "vertex_ai/gemini-3.5-flash-lite"},
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt == build_not_configured_agent_gateway_status(
        context="fresh_debate.live_execution"
    )
    assert receipt["status"] == "not_configured"
    assert receipt["egress_decision"]["blocked"] is False
    assert receipt["decision_authority"] == "none"


def test_local_gateway_allows_configured_route_and_tool() -> None:
    gateway = LocalPolicyAgentGateway()

    receipt = gateway.evaluate_egress(
        model_routes={
            "generator": "vertex_ai/gemini-3.5-flash-lite",
            "judge": "vertex_ai/gemini-3.6-flash",
        },
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "configured"
    assert receipt["decision_authority"] == "routing_and_egress_only"
    assert receipt["egress_decision"] == {
        "checked": True,
        "blocked": False,
        "context": "fresh_debate.live_execution",
        "reason": "passed",
    }
    assert receipt["model_route_policy"]["blocked"] is False
    assert receipt["tool_egress_policy"]["blocked"] is False


def test_local_gateway_blocks_disallowed_model_route() -> None:
    gateway = LocalPolicyAgentGateway()

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "unapproved/provider"},
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "blocked"
    assert receipt["egress_decision"]["blocked"] is True
    assert receipt["egress_decision"]["reason"] == "model_route_blocked"
    assert receipt["model_route_policy"]["rejected_routes"] == [
        "unapproved/provider"
    ]


def test_local_gateway_blocks_disallowed_tool() -> None:
    gateway = LocalPolicyAgentGateway(allowed_tools=["fresh_debate"])

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "vertex_ai/gemini-3.5-flash-lite"},
        tool_names=["fresh_debate", "exfiltrate_artifacts"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "blocked"
    assert receipt["egress_decision"]["blocked"] is True
    assert receipt["egress_decision"]["reason"] == "tool_egress_blocked"
    assert receipt["tool_egress_policy"]["rejected_tools"] == [
        "exfiltrate_artifacts"
    ]


def test_gateway_factory_reads_pipe_delimited_env_values() -> None:
    gateway = build_agent_gateway(
        env={
            "BARRED_AGENT_GATEWAY_MODE": "local_policy",
            "BARRED_AGENT_GATEWAY_ALLOWED_MODEL_ROUTES": "approved/a|approved/b",
            "BARRED_AGENT_GATEWAY_ALLOWED_TOOLS": "fresh_debate|report_barred_run",
        }
    )

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "approved/a", "judge": "denied/c"},
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "blocked"
    assert receipt["model_route_policy"]["allowed_routes"] == [
        "approved/a",
        "approved/b",
    ]
    assert receipt["model_route_policy"]["rejected_routes"] == ["denied/c"]


def test_cloud_gateway_missing_configuration_blocks_fail_closed() -> None:
    gateway = CloudAgentGateway(project_id="", location_id="us-east1", gateway_id="")

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "vertex_ai/gemini-3.5-flash-lite"},
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "error"
    assert receipt["mode"] == "cloud_agent_gateway"
    assert receipt["egress_decision"]["blocked"] is True
    assert receipt["egress_decision"]["reason"] == (
        "missing_agent_gateway_configuration"
    )


def test_cloud_gateway_allows_after_control_plane_verification() -> None:
    gateway_resource = (
        "projects/gem-creation/locations/us-east1/agentGateways/barred-egress-v1"
    )
    client = FakeCloudGatewayClient(
        response={
            "name": gateway_resource,
            "googleManaged": {"governedAccessPath": "AGENT_TO_ANYWHERE"},
        }
    )
    gateway = CloudAgentGateway(
        project_id="gem-creation",
        location_id="us-east1",
        gateway_id="barred-egress-v1",
        policy_id="barred-egress-policy-v1",
        client=client,
    )

    receipt = gateway.evaluate_egress(
        model_routes={
            "generator": "vertex_ai/gemini-3.5-flash-lite",
            "judge": "vertex_ai/gemini-3.6-flash",
        },
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert client.requests == [gateway_resource]
    assert receipt["status"] == "configured"
    assert receipt["cloud_control_plane"]["checked"] is True
    assert receipt["cloud_control_plane"]["gateway_resource"] == gateway_resource
    assert receipt["cloud_control_plane"]["governed_access_path"] == (
        "AGENT_TO_ANYWHERE"
    )
    assert receipt["egress_decision"]["blocked"] is False
    assert receipt["egress_decision"]["reason"] == "passed"


def test_cloud_gateway_blocks_disallowed_route_after_gateway_verification() -> None:
    gateway_resource = (
        "projects/gem-creation/locations/us-east1/agentGateways/barred-egress-v1"
    )
    client = FakeCloudGatewayClient(response={"name": gateway_resource})
    gateway = CloudAgentGateway(
        project_id="gem-creation",
        location_id="us-east1",
        gateway_id="barred-egress-v1",
        client=client,
        allowed_model_routes=["vertex_ai/gemini-3.6-flash"],
    )

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "vertex_ai/gemini-3.5-flash-lite"},
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "blocked"
    assert receipt["mode"] == "cloud_agent_gateway"
    assert receipt["model_route_policy"]["rejected_routes"] == [
        "vertex_ai/gemini-3.5-flash-lite"
    ]
    assert receipt["egress_decision"]["reason"] == "model_route_blocked"


def test_cloud_gateway_provider_error_blocks_fail_closed() -> None:
    gateway = CloudAgentGateway(
        project_id="gem-creation",
        location_id="us-east1",
        gateway_id="barred-egress-v1",
        client=FakeCloudGatewayClient(error=RuntimeError("unreachable")),
    )

    receipt = gateway.evaluate_egress(
        model_routes={"generator": "vertex_ai/gemini-3.5-flash-lite"},
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )

    assert receipt["status"] == "error"
    assert receipt["egress_decision"]["blocked"] is True
    assert receipt["egress_decision"]["reason"] == "cloud_agent_gateway_unavailable"
    assert receipt["egress_decision"]["error_type"] == "RuntimeError"


def test_gateway_factory_builds_cloud_gateway_from_env() -> None:
    gateway = build_agent_gateway(
        env={
            "BARRED_AGENT_GATEWAY_MODE": "cloud_agent_gateway",
            "GOOGLE_CLOUD_PROJECT": "gem-creation",
            "GOOGLE_CLOUD_LOCATION": "us-east1",
            "BARRED_AGENT_GATEWAY_ID": "barred-egress-v1",
            "BARRED_AGENT_GATEWAY_POLICY_ID": "barred-egress-policy-v1",
            "BARRED_AGENT_GATEWAY_AUDIT_ONLY": "true",
        }
    )

    assert isinstance(gateway, CloudAgentGateway)
    assert gateway.project_id == "gem-creation"
    assert gateway.location_id == "us-east1"
    assert gateway.gateway_id == "barred-egress-v1"
    assert gateway.policy_id == "barred-egress-policy-v1"
    assert gateway.audit_only is True

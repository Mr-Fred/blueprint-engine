import pytest
import asyncio
from app.types import SecurityRubricEvaluation, SRERubricEvaluation, STRIDEThreatEntry
from app.agents.security.agent import security_agent_node
from app.agents.sre.agent import sre_agent_node
from google.adk.agents.context import Context
from app.config import settings

def test_rubric_schemas_validation():
    sec_rubric = SecurityRubricEvaluation(
        data_protection_score=0.95,
        identity_access_score=0.88,
        vulnerability_surface_area="LOW",
        stride_threat_register=[
            STRIDEThreatEntry(
                category="SPOOFING",
                threat_title="Token Replay",
                component="API Gateway",
                severity="HIGH",
                mitigation_status="Use mTLS + short-lived JWTs"
            )
        ],
        detailed_critique="### Verified Security Posture"
    )
    assert sec_rubric.data_protection_score == 0.95
    assert len(sec_rubric.stride_threat_register) == 1

    sre_rubric = SRERubricEvaluation(
        high_availability_score=0.99,
        fault_tolerance_score=0.92,
        observability_score=0.90,
        estimated_uptime_tier="99.99%",
        detailed_critique="### Verified Resilience Posture"
    )
    assert sre_rubric.estimated_uptime_tier == "99.99%"


from types import SimpleNamespace

@pytest.mark.asyncio
async def test_security_and_sre_nodes_produce_rubric_in_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", True)
    ctx = SimpleNamespace(state={"project_id": "test_rubric_proj", "current_round": 1})

    # Run security node
    sec_generator = security_agent_node._func(ctx, {"proposal": "Test Proposal"})
    events = []
    async for event in sec_generator:
        events.append(event)

    assert "latest_security_rubric" in ctx.state
    sec_dump = ctx.state["latest_security_rubric"]
    assert sec_dump["vulnerability_surface_area"] == "LOW"
    assert sec_dump["data_protection_score"] >= 0.0

    # Run SRE node
    sre_generator = sre_agent_node._func(ctx, {"proposal": "Test Proposal"})
    async for event in sre_generator:
        pass

    assert "latest_sre_rubric" in ctx.state
    sre_dump = ctx.state["latest_sre_rubric"]
    assert sre_dump["estimated_uptime_tier"] == "99.99%"

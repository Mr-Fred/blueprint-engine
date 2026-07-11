import pytest
from app.harness.sandbox import (
    LeadArchitectWorkspace,
    SecurityAuditorWorkspace,
    SREAuditorWorkspace,
)


def test_lead_architect_workspace():
    catalog = LeadArchitectWorkspace.get_pattern_catalog()
    assert "event_sourcing" in catalog
    aws_components = LeadArchitectWorkspace.get_cloud_reference("aws_serverless")
    assert "Lambda" in aws_components


def test_security_auditor_workspace():
    stride = SecurityAuditorWorkspace.get_owasp_threat_vectors()
    assert "Spoofing" in stride
    hipaa = SecurityAuditorWorkspace.get_compliance_checklist("HIPAA")
    assert any("PHI" in item for item in hipaa)


def test_sre_auditor_workspace_composite_sla():
    slas = [99.9, 99.9]
    composite = SREAuditorWorkspace.calculate_composite_availability(slas)
    assert composite == round(0.999 * 0.999, 6)

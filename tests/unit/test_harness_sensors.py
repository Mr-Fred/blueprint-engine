import pytest
from app.harness.sensors import (
    DiagramSyntaxSensor,
    LeftShiftedBlueprintPipeline,
)
from app.harness.ledger import EpistemicScratchpad


def test_diagram_syntax_sensor_validates_mermaid():
    """Test pure-Python Mermaid structural validator."""
    valid_md = """
Here is our architecture:
```mermaid
graph TD
    A[Client] --> B[API Gateway]
    B --> C[PostgreSQL]
```
"""
    assert DiagramSyntaxSensor.validate_diagrams(valid_md) == []

    invalid_brackets = """
```mermaid
graph TD
    A[Client --> B[API Gateway]
```
"""
    errors = DiagramSyntaxSensor.validate_diagrams(invalid_brackets)
    assert len(errors) == 1
    assert "Mismatched square brackets" in errors[0]


def test_left_shifted_pipeline_envelope_schema_failure():
    """Test Layer 0 catches bad envelope structure."""
    bad_payload = {"missing_proposal": True}
    res = LeftShiftedBlueprintPipeline.run_pipeline(bad_payload, "proj_test")
    assert not res.passed
    assert res.failed_layer == "Layer 0: Envelope Schema"
    assert res.formatted_backpressure is not None
    assert "HARNESS AUTOMATED SENSOR INTERCEPTION" in res.formatted_backpressure


def test_left_shifted_pipeline_epistemic_consistency_failure(tmp_path, monkeypatch):
    """Test Layer 2 catches proposals contradicting the Epistemic Scratchpad."""
    from app.utils import FilesystemJail
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path)

    scratchpad = EpistemicScratchpad(project_id="proj_epistemic")
    scratchpad.add_fact("All storage must use postgres only", "Security")

    payload = {
        "proposal": "We will store session tokens in DynamoDB table.",
        "round_number": 1,
    }
    res = LeftShiftedBlueprintPipeline.run_pipeline(payload, "proj_epistemic", scratchpad)
    assert not res.passed
    assert res.failed_layer == "Layer 2: Epistemic Consistency"
    assert "contradicts Epistemic Scratchpad fact" in res.errors[0]


def test_artifact_syntax_validator_and_multi_file_writer(tmp_path, monkeypatch):
    """Test programmatic fail-safe validation and sandboxed file writing for ADK 2.0 multi-file tracks."""
    from app.harness.sensors import ArtifactSyntaxValidator
    from app.harness.tools import HarnessToolRegistry
    from app.utils import FilesystemJail

    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path)

    valid_json = '{"threat_model": "STRIDE", "status": "verified"}'
    invalid_json = '{"threat_model": "STRIDE", trailing_comma: }'
    assert ArtifactSyntaxValidator.validate_artifact("security/risk_matrix.json", valid_json) == []
    assert len(ArtifactSyntaxValidator.validate_artifact("security/risk_matrix.json", invalid_json)) > 0

    valid_mmd = "graph TD\n  A --> B"
    invalid_mmd = "graph TD\n  A -->"
    assert ArtifactSyntaxValidator.validate_artifact("diagrams/topology.mmd", valid_mmd) == []
    assert len(ArtifactSyntaxValidator.validate_artifact("diagrams/topology.mmd", invalid_mmd)) > 0

    success_msg = HarnessToolRegistry.write_synthesized_artifact(
        "proj_test_multi", "diagrams/topology.mmd", valid_mmd
    )
    assert success_msg.startswith("SUCCESS:")
    assert (tmp_path / "proj_test_multi" / "diagrams" / "topology.mmd").exists()

    err_msg = HarnessToolRegistry.write_synthesized_artifact(
        "proj_test_multi", "diagrams/bad.mmd", invalid_mmd
    )
    assert err_msg.startswith("VALIDATION_ERROR:")
    assert not (tmp_path / "proj_test_multi" / "diagrams" / "bad.mmd").exists()


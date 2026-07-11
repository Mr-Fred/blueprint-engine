import pytest
from pathlib import Path
from app.main import resolve_project_artifacts, DEBATE_SESSIONS
from app.types import DebateState
from app.utils import FilesystemJail

def test_resolve_project_artifacts_multi_file(tmp_path, monkeypatch):
    project_id = "test_multi_file_proj"
    DEBATE_SESSIONS[project_id] = DebateState(
        project_id=project_id,
        concept="Multi-File Architecture Test",
        current_round=3,
        rounds_history=[]
    )

    # Monkeypatch jail base dir to tmp_path
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path.resolve())

    # Write sample ADK 2.0 multi-file tracks inside jailed output folder
    out_dir = tmp_path / project_id
    (out_dir / "docs").mkdir(parents=True, exist_ok=True)
    (out_dir / "diagrams").mkdir(parents=True, exist_ok=True)
    (out_dir / "security").mkdir(parents=True, exist_ok=True)

    (out_dir / "docs/prd.md").write_text("# PRD Specification\nTarget RPS: 5000", encoding="utf-8")
    (out_dir / "ARCHITECTURE.md").write_text("# System Architecture\nHexagonal layers", encoding="utf-8")
    (out_dir / "diagrams/topology.mmd").write_text("graph TD\n  Client --> API", encoding="utf-8")
    (out_dir / "security/risk_matrix.json").write_text('{"threats": [{"threat": "SQLi", "severity": "HIGH"}]}', encoding="utf-8")

    resolve_project_artifacts(project_id)

    state = DEBATE_SESSIONS[project_id]
    assert state.final_prd == "# PRD Specification\nTarget RPS: 5000"
    assert state.final_architecture == "# System Architecture\nHexagonal layers"
    assert state.final_topology == "graph TD\n  Client --> API"
    assert state.final_risk_matrix == '{"threats": [{"threat": "SQLi", "severity": "HIGH"}]}'
    assert state.final_artifacts["docs/prd.md"] == "# PRD Specification\nTarget RPS: 5000"
    assert state.final_artifacts["diagrams/topology.mmd"] == "graph TD\n  Client --> API"
    assert state.final_artifacts["security/risk_matrix.json"] == '{"threats": [{"threat": "SQLi", "severity": "HIGH"}]}'
    assert state.consensus_achieved is True

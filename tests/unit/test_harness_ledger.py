import pytest
from pathlib import Path
from app.harness.ledger import GlobalArchitectureLedger, EpistemicScratchpad, FactEntry
from app.utils import FilesystemJail


def test_global_architecture_ledger_save_and_load(tmp_path, monkeypatch):
    """Test that GlobalArchitectureLedger persists and reloads correctly."""
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path)
    project_id = "test_ledger_proj"

    ledger = GlobalArchitectureLedger(project_id=project_id)
    event = ledger.update_baseline(
        summary="Microservices with Event Sourcing",
        components={"db": "PostgreSQL 16", "broker": "Kafka"},
    )

    assert event.event_type == "BaselineArchitectureUpdated"
    assert ledger.baseline_summary == "Microservices with Event Sourcing"

    loaded = GlobalArchitectureLedger.load(project_id)
    assert loaded.baseline_summary == "Microservices with Event Sourcing"
    assert loaded.decided_components["db"] == "PostgreSQL 16"


def test_epistemic_scratchpad_add_fact_and_contradiction(tmp_path, monkeypatch):
    """Test EpistemicScratchpad fact logging and contradiction detection."""
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path)
    project_id = "test_scratchpad_proj"

    scratchpad = EpistemicScratchpad(project_id=project_id)
    event = scratchpad.add_fact(statement="All data must use postgres only", verifier="SecurityAuditor")

    assert event.event_type == "EpistemicFactAdded"
    assert len(scratchpad.verified_facts) == 1

    conflict = scratchpad.check_contradiction("We should use dynamodb for storage")
    assert conflict is not None
    assert conflict.fact_id == "fact_1"

    no_conflict = scratchpad.check_contradiction("We will index users table in postgres")
    assert no_conflict is None

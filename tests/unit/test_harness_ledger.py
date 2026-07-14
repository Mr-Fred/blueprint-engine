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


def test_epistemic_scratchpad_idempotent_deduplication(tmp_path, monkeypatch):
    """Test EpistemicScratchpad idempotent deduplication and round prefix update."""
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path)
    scratchpad = EpistemicScratchpad(project_id="test_idempotency_proj")

    # 1. Exact duplicate check
    evt1 = scratchpad.add_fact("Spanner uses multi-region deployment", verifier="LeadArchitect")
    assert evt1.event_type == "EpistemicFactAdded"
    evt2 = scratchpad.add_fact("Spanner uses multi-region deployment", verifier="LeadArchitect")
    assert evt2.event_type == "EpistemicFactUnchanged"
    assert len(scratchpad.verified_facts) == 1

    # 2. Keyed prefix update check
    evt3 = scratchpad.add_fact("Round 1 Architectural Design Decision: Original draft", verifier="JudgeAgent")
    assert evt3.event_type == "EpistemicFactAdded"
    evt4 = scratchpad.add_fact("Round 1 Architectural Design Decision: Updated refined draft", verifier="JudgeAgent")
    assert evt4.event_type == "EpistemicFactUpdated"
    assert len(scratchpad.verified_facts) == 2
    assert "Updated refined draft" in scratchpad.verified_facts[1].statement


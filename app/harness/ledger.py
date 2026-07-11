import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.utils import FilesystemJail

logger = logging.getLogger(__name__)


class FactEntry(BaseModel):
    """Represents a mutually verified fact logged in the Epistemic Scratchpad."""
    fact_id: str = Field(..., description="Unique identifier for the fact")
    statement: str = Field(..., description="The verified statement agreed upon by agents")
    verifier: str = Field(..., description="Role that verified or established this fact")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp when fact was verified",
    )


class LedgerEvent(BaseModel):
    """Immutable domain event recorded in the Event Store stream."""
    event_id: str = Field(..., description="Unique event ID")
    event_type: str = Field(..., description="Type of ledger event")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event data")


class GlobalArchitectureLedger(BaseModel):
    """
    Central baseline design ledger for a project session.
    Updated only upon consensus or verified architectural decisions.
    """
    project_id: str = Field(..., description="The project identifier")
    baseline_summary: Optional[str] = Field(None, description="Summary of current baseline design")
    decided_components: Dict[str, Any] = Field(default_factory=dict, description="Locked component specifications")
    last_updated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )

    def update_baseline(self, summary: str, components: Optional[Dict[str, Any]] = None) -> LedgerEvent:
        """Updates the baseline design and returns an immutable LedgerEvent."""
        self.baseline_summary = summary
        if components:
            self.decided_components.update(components)
        self.last_updated = datetime.now(timezone.utc).isoformat()
        
        event = LedgerEvent(
            event_id=f"evt_ledger_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            event_type="BaselineArchitectureUpdated",
            payload={
                "project_id": self.project_id,
                "baseline_summary": self.baseline_summary,
                "decided_components": self.decided_components,
            },
        )
        self.save()
        return event

    def save(self) -> None:
        """Persists the architecture ledger to the project sandbox directory."""
        try:
            FilesystemJail.write_project_file(
                self.project_id,
                "architecture_ledger.json",
                self.model_dump_json(indent=2),
            )
        except Exception as e:
            logger.error(f"Failed to persist GlobalArchitectureLedger for {self.project_id}: {e}")

    @classmethod
    def load(cls, project_id: str) -> "GlobalArchitectureLedger":
        """Loads an existing ledger or creates a new empty ledger if none exists."""
        try:
            content = FilesystemJail.read_project_file(project_id, "architecture_ledger.json")
            return cls.model_validate_json(content)
        except Exception:
            return cls(project_id=project_id)


class EpistemicScratchpad(BaseModel):
    """
    Shared scratchpad holding mutually verified facts to prevent hallucination divergence.
    """
    project_id: str = Field(..., description="The project identifier")
    verified_facts: List[FactEntry] = Field(default_factory=list, description="List of verified facts")

    def add_fact(self, statement: str, verifier: str = "LeadArchitect") -> LedgerEvent:
        """Appends a new mutually verified fact and emits a LedgerEvent."""
        fact_id = f"fact_{len(self.verified_facts) + 1}"
        entry = FactEntry(fact_id=fact_id, statement=statement, verifier=verifier)
        self.verified_facts.append(entry)
        self.save()

        return LedgerEvent(
            event_id=f"evt_fact_{fact_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            event_type="EpistemicFactAdded",
            payload=entry.model_dump(),
        )

    def record_round_facts(self, ctx: Any, proposal: str, current_round: int) -> "EpistemicScratchpad":
        """
        Extracts factual domain requirements (performance_targets, scale_requirements, technical_constraints)
        and architectural design decisions from a round proposal into verified facts.
        """
        if len(self.verified_facts) == 0:
            concept = ctx.state.get("concept")
            if concept:
                self.add_fact(
                    statement=f"System Concept & Scope: {concept}",
                    verifier="DiscoveryGrilling",
                )
            reqs = ctx.state.get("requirements")
            if reqs:
                req_dict = reqs.model_dump() if hasattr(reqs, "model_dump") else (reqs if isinstance(reqs, dict) else {})
                for key, label in [
                    ("performance_targets", "Performance Target"),
                    ("scale_requirements", "Scale Requirement"),
                    ("technical_constraints", "Technical Constraints"),
                ]:
                    val = req_dict.get(key)
                    if val:
                        self.add_fact(
                            statement=f"Verified {label}: {val}",
                            verifier="DiscoveryGrilling",
                        )

        clean_prop = [p.strip() for p in proposal.split("\n\n") if p.strip() and not p.strip().startswith("#")][:2]
        proposal_snippet = " ".join(clean_prop)[:350] if clean_prop else proposal[:350]
        self.add_fact(
            statement=f"Round {current_round} Architectural Design Decision: {proposal_snippet}",
            verifier="JudgeAgent",
        )
        return self

    def check_contradiction(self, statement: str) -> Optional[FactEntry]:
        """
        Lightweight keyword consistency check against locked facts.
        Returns the contradictory FactEntry if a direct conflict is detected.
        """
        stmt_lower = statement.lower()
        for fact in self.verified_facts:
            f_lower = fact.statement.lower()
            # Check simple opposing pairs e.g. "http only" vs "https/tls" or "dynamodb" vs "postgres only"
            if "must use postgres" in f_lower and "dynamodb" in stmt_lower:
                return fact
            if "must be encrypted" in f_lower and "unencrypted" in stmt_lower:
                return fact
        return None

    def save(self) -> None:
        """Persists the epistemic scratchpad to the project sandbox directory."""
        try:
            FilesystemJail.write_project_file(
                self.project_id,
                "epistemic_scratchpad.json",
                self.model_dump_json(indent=2),
            )
        except Exception as e:
            logger.error(f"Failed to persist EpistemicScratchpad for {self.project_id}: {e}")

    @classmethod
    def load(cls, project_id: str) -> "EpistemicScratchpad":
        """Loads an existing scratchpad or creates a new empty one."""
        try:
            content = FilesystemJail.read_project_file(project_id, "epistemic_scratchpad.json")
            return cls.model_validate_json(content)
        except Exception:
            return cls(project_id=project_id)

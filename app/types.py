from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class PillarScores(BaseModel):
    performance: float = Field(..., ge=0.0, le=1.0, description="Performance score from 0.0 to 1.0 (Latency, throughput, and hot path execution)")
    scalability: float = Field(..., ge=0.0, le=1.0, description="Scalability score from 0.0 to 1.0 (Horizontal scaling, data storage growth, and compute bounds)")
    security: float = Field(..., ge=0.0, le=1.0, description="Security score from 0.0 to 1.0 (CIA triad, auth patterns, IAM roles, and transit/rest encryption)")
    reliability: float = Field(..., ge=0.0, le=1.0, description="Reliability score from 0.0 to 1.0 (Fault tolerance, HA, disaster recovery, and failover mechanics)")
    maintainability: float = Field(..., ge=0.0, le=1.0, description="Maintainability score from 0.0 to 1.0 (Paradigm clarity, modular boundary separation, and tech debt index)")
    cost_efficiency: float = Field(..., ge=0.0, le=1.0, description="Cost Efficiency score from 0.0 to 1.0 (Hosting bills, compute sizing, and serverless/database spend optimization)")

    def meets_threshold(self, threshold: float = 0.85) -> bool:
        """Helper to verify if all 6 quality pillars independently meet or exceed the consensus threshold."""
        return (
            self.performance >= threshold
            and self.scalability >= threshold
            and self.security >= threshold
            and self.reliability >= threshold
            and self.maintainability >= threshold
            and self.cost_efficiency >= threshold
        )

class DebateRound(BaseModel):
    round_number: int = Field(..., description="The turn sequence index of the debate")
    proposal_draft: str = Field(..., description="The architectural draft proposed by the Lead Architect / performance specialist")
    critique: str = Field(..., description="The combined audits and criticisms compiled by the security and DevOps agents")
    scores: PillarScores = Field(..., description="The metrics scored for this design turn across all 6 attributes")
    judge_directive: Optional[str] = Field(None, description="Global human feedback directive published in this round, if any")

class DebateState(BaseModel):
    project_id: str = Field(..., description="The unique session identifier linked to the output subdirectory")
    concept: str = Field(..., description="The high-level software idea being architected")
    current_round: int = Field(default=1, description="The current active round index")
    rounds_history: List[DebateRound] = Field(default_factory=list, description="All previous debate round exchanges")
    grill_history: List[Dict[str, str]] = Field(default_factory=list, description="Chat log of the initial architectural grilling phase")
    consensus_achieved: bool = Field(default=False, description="True if all 6 pillar scores meet or exceed threshold")
    final_prd: Optional[str] = Field(None, description="The finalized Product Requirements Document (PRD)")
    final_architecture: Optional[str] = Field(None, description="The finalized Architecture Design document")
    latest_proposal: Optional[str] = Field(None, description="The most recent proposal draft")
    latest_judge_directive: Optional[str] = Field(None, description="The active or pending judge feedback directive")
    force_synthesis_flag: bool = Field(default=False, description="Flag to immediately synthesize blueprints regardless of scores")

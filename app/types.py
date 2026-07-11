from pydantic import BaseModel, Field, field_validator
import re
from typing import Any, Dict, List, Literal, Optional

class STRIDEThreatEntry(BaseModel):
    """Explicit mapping of a STRIDE threat to an architectural component."""
    category: Literal["SPOOFING", "TAMPERING", "REPUDIATION", "INFORMATION_DISCLOSURE", "DENIAL_OF_SERVICE", "ELEVATION_OF_PRIVILEGE"] = Field(..., description="STRIDE threat category")
    threat_title: str = Field(..., description="Short descriptive title of the vulnerability")
    component: str = Field(..., description="Target architectural component or boundary")
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(..., description="Severity rating")
    mitigation_status: str = Field(..., description="Recommended architectural hardening action")


class SecurityRubricEvaluation(BaseModel):
    """Google ADK 2.0 structured output schema for the Security Auditor."""
    data_protection_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score (0.0-1.0) verifying encryption at rest/transit and perimeter isolation")
    identity_access_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score (0.0-1.0) checking least-privilege role bindings, gateway auth, and token hygiene")
    vulnerability_surface_area: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Relative attack surface rating")
    stride_threat_register: List[STRIDEThreatEntry] = Field(default_factory=list, description="Array mapping threats to architectural components")
    detailed_critique: str = Field(..., description="Comprehensive markdown security review explaining vulnerabilities and hardening advice")


class SRERubricEvaluation(BaseModel):
    """Google ADK 2.0 structured output schema for the SRE Auditor."""
    high_availability_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score (0.0-1.0) evaluating multi-region/AZ topology and SPOF elimination")
    fault_tolerance_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score (0.0-1.0) verifying circuit breakers, exponential backoff, retry queues, and rate limits")
    observability_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score (0.0-1.0) checking distributed tracing, metrics, and structured logs")
    estimated_uptime_tier: Literal["99.9%", "99.99%", "SUB_99%"] = Field(..., description="Target SLA availability tier mapped to proposed design choices")
    detailed_critique: str = Field(..., description="Comprehensive markdown SRE review explaining resilience, SLOs, and scalability trade-offs")


class PillarScores(BaseModel):
    performance: float = Field(..., ge=0.0, le=1.0, description="Performance score from 0.0 to 1.0 (Latency, throughput, and hot path execution)")
    scalability: float = Field(..., ge=0.0, le=1.0, description="Scalability score from 0.0 to 1.0 (Horizontal scaling, data storage growth, and compute bounds)")
    security: float = Field(..., ge=0.0, le=1.0, description="Security score from 0.0 to 1.0 (CIA triad, auth patterns, IAM roles, and transit/rest encryption)")
    reliability: float = Field(..., ge=0.0, le=1.0, description="Reliability score from 0.0 to 1.0 (Fault tolerance, HA, disaster recovery, and failover mechanics)")
    maintainability: float = Field(..., ge=0.0, le=1.0, description="Maintainability score from 0.0 to 1.0 (Paradigm clarity, modular boundary separation, and tech debt index)")
    cost_efficiency: float = Field(..., ge=0.0, le=1.0, description="Cost Efficiency score from 0.0 to 1.0 (Hosting bills, compute sizing, and serverless/database spend optimization)")

    @field_validator("performance", "scalability", "security", "reliability", "maintainability", "cost_efficiency", mode="before")
    @classmethod
    def parse_float_score(cls, value: Any) -> float:
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        if isinstance(value, str):
            match = re.search(r"([0-9]*\.?[0-9]+)", value)
            if match:
                val = float(match.group(1))
                return max(0.0, min(1.0, val))
        return 0.85

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

class RequirementsSchema(BaseModel):
    """Structured requirements extracted during Phase 1 Discovery Grilling."""
    preferred_tech_stack: List[str] = Field(default_factory=list, description="Preferred languages, databases, frameworks")
    cloud_provider: Optional[str] = Field(None, description="Preferred cloud provider e.g. AWS, GCP, Azure")
    architectural_pattern: Optional[str] = Field(None, description="Desired pattern e.g. Event Sourcing, Clean Architecture")
    target_rps: Optional[int] = Field(None, description="Target requests per second or scale requirement")
    budget_tier: Optional[str] = Field(None, description="Budget constraint or tier e.g. Serverless/Low-cost vs Enterprise HA")
    compliance_frameworks: List[str] = Field(default_factory=list, description="Required compliance standards e.g. SOC2, GDPR, HIPAA")
    core_use_cases: List[str] = Field(default_factory=list, description="Primary user journeys or core functional capabilities")


class DebateState(BaseModel):
    project_id: str = Field(..., description="The unique session identifier linked to the output subdirectory")
    concept: str = Field(..., description="The high-level software idea being architected")
    current_round: int = Field(default=1, description="The current active round index")
    max_rounds: int = Field(default=3, description="Maximum number of debate rounds permitted")
    rounds_history: List[DebateRound] = Field(default_factory=list, description="All previous debate round exchanges")
    grill_history: List[Dict[str, str]] = Field(default_factory=list, description="Chat log of the initial architectural grilling phase")
    consensus_achieved: bool = Field(default=False, description="True if all 6 pillar scores meet or exceed threshold")
    final_prd: Optional[str] = Field(None, description="The finalized Product Requirements Document (PRD)")
    final_architecture: Optional[str] = Field(None, description="The finalized Architecture Design document")
    final_topology: Optional[str] = Field(None, description="The finalized Mermaid topology diagram (diagrams/topology.mmd)")
    final_risk_matrix: Optional[str] = Field(None, description="The finalized Security Risk Matrix JSON (security/risk_matrix.json)")
    final_artifacts: Dict[str, str] = Field(default_factory=dict, description="Map of all synthesized relative paths to their raw contents")
    latest_proposal: Optional[str] = Field(None, description="The most recent proposal draft")
    latest_security_critique: Optional[str] = Field(None, description="The most recent security critique")
    latest_security_rubric: Optional[SecurityRubricEvaluation] = Field(None, description="Structured Security ADK 2.0 evaluation rubric")
    latest_sre_critique: Optional[str] = Field(None, description="The most recent SRE critique")
    latest_sre_rubric: Optional[SRERubricEvaluation] = Field(None, description="Structured SRE ADK 2.0 evaluation rubric")
    latest_judge_directive: Optional[str] = Field(None, description="The active or pending judge feedback directive")
    force_synthesis_flag: bool = Field(default=False, description="Flag to immediately synthesize blueprints regardless of scores")
    caveman_mode: bool = Field(default=True, description="Whether to enable ultra-compressed caveman communication mode by default")
    grill_interaction_id: Optional[str] = Field(None, description="Active Interactions API session id for grilling phase")
    grill_question_count: int = Field(default=0, description="Counter for clarifying questions asked during interview")
    grill_completed: bool = Field(default=False, description="True when the grilling interview has completed or been skipped")
    requirements: Optional[RequirementsSchema] = Field(None, description="Extracted requirements from Discovery Grilling")
    intermission_paused: bool = Field(default=False, description="True if debate graph is paused at HITL intermission")
    intermission_action: Optional[str] = Field(None, description="Last recorded intermission action")
    performance_interaction_id: Optional[str] = Field(None, description="Interactions API session id for performance agent")
    security_interaction_id: Optional[str] = Field(None, description="Interactions API session id for security agent")
    sre_interaction_id: Optional[str] = Field(None, description="Interactions API session id for sre agent")
    epistemic_scratchpad: Optional[Dict[str, Any]] = Field(None, description="Serialized Epistemic Scratchpad facts")
    journey_trace: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Chronological telemetry spans tracking end-to-end user journey")


class DebateRoundEnvelope(BaseModel):
    """Typed event envelope passed across graph seams to prevent leaky context reads."""
    proposal: str = Field(..., description="The architectural draft proposed by performance_agent_node")
    security_critique: Optional[str] = Field(None, description="Critique generated by security_agent_node")
    sre_critique: Optional[str] = Field(None, description="Critique generated by sre_agent_node")
    round_number: int = Field(default=1, description="The round sequence index")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional envelope metadata")



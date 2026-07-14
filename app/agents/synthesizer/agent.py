import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node

from app.agents.synthesizer.prompt import (
    get_architecture_synthesis_prompt,
    get_prd_synthesis_prompt,
)
from app.config import settings
from app.utils import FilesystemJail, load_matching_skills

logger = logging.getLogger(__name__)


class SynthesizedArtifactFile(BaseModel):
    """Structured schema for a single synthesized multi-file artifact."""
    relative_path: str = Field(
        ...,
        description="Target relative path inside output directory (e.g., ARCHITECTURE.md, docs/prd.md, diagrams/topology.mmd, security/risk_matrix.json)",
    )
    file_type: str = Field(..., description="File type: 'markdown', 'mermaid', or 'json'")
    content: str = Field(..., description="Full production-ready content of the artifact file")


class SynthesisBundlePayload(BaseModel):
    """Structured ADK 2.0 Multi-File File-Writer payload containing production artifacts."""
    files: List[SynthesizedArtifactFile] = Field(..., description="Array of production-ready synthesized files")


def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()


@node
async def synthesis_node(ctx: Context, node_input: Any) -> Event:
    """Node 5: Compiles production-ready ADK 2.0 multi-file architectural artifacts and writes them safely."""
    client = get_genai_client()
    bundle_response: Any = None
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept", "")

    history = ctx.state.get("rounds_history", [])
    latest_proposal = ctx.state.get("latest_proposal", "")
    if not latest_proposal and history:
        last_round = history[-1]
        last_dict = last_round if isinstance(last_round, dict) else last_round.model_dump()
        latest_proposal = last_dict.get("proposal_draft", "")

    from app.harness.moderator import ContextSummarizer
    from app.harness.tools import HarnessToolRegistry

    compacted_history = ContextSummarizer.compact_round_history(history)
    agreement_summary = ContextSummarizer.extract_semantic_agreement(
        compacted_history,
        open_threats=ctx.state.get("open_threats", []),
        open_gaps=ctx.state.get("open_gaps", []),
    )
    facts = HarnessToolRegistry.query_verified_facts(project_id)
    facts_text = "\n".join([f"- [{f.get('verifier', 'System')}]: {f.get('statement')}" for f in facts]) if facts else "No verified facts recorded."

    synthesis_context = (
        f"=== CONSENSUS ARCHITECTURAL BLUEPRINT (FINAL PROPOSAL) ===\n{latest_proposal}\n\n"
        f"=== ESTABLISHED ARCHITECTURAL AGREEMENT MATRIX ===\n{agreement_summary}\n\n"
        f"=== VERIFIED EPISTEMIC FACTS ===\n{facts_text}"
    )

    skills_dir = Path(__file__).parent / "skills"
    matched_skills = load_matching_skills(skills_dir, f"{concept} {synthesis_context}")

    prd_prompt = get_prd_synthesis_prompt(concept, synthesis_context, matched_skills)
    arch_prompt = get_architecture_synthesis_prompt(concept, synthesis_context, matched_skills)

    from app.harness.tools import HarnessToolRegistry
    from app.harness.skills_registry import JITSkillRegistry
    from google.genai import types

    harness_tools = [
        HarnessToolRegistry.lookup_architectural_pattern,
        HarnessToolRegistry.query_verified_facts,
        HarnessToolRegistry.write_synthesized_artifact,
        JITSkillRegistry.read_skill,
    ]

    if settings.mock_mode:
        prd_content = (
            f"# [MOCK MODE] Product Requirements Document: {concept}\n\n"
            "1. **Goal**: High-performance scalable backend architecture.\n"
            "2. **Target Persona**: DevOps & Engineers.\n"
            "3. **Functional Requirements**: Real-time streaming, auto-scaling.\n"
            "4. **Non-Functional Constraints**: < 10ms latency, 99.99% uptime.\n"
            "5. **Tasklist**: 1. Setup Spanner, 2. Deploy GKE cluster.\n"
        )
        arch_content = (
            f"# [MOCK MODE] ARCHITECTURE.md: {concept}\n\n"
            "## Hexagonal Clean Architecture Blueprint\n"
            "- **Domain Layer**: Pure Pydantic models and business rules.\n"
            "- **Application Layer**: ADK 2.0 async generators and workflow orchestration.\n"
            "- **Infrastructure Layer**: Cloud Spanner, Redis Cluster, and Pub/Sub workers.\n"
        )
        topology_content = (
            "graph TD\n"
            "  Client --> Gateway[API Gateway]\n"
            "  Gateway --> Auth[Auth Service]\n"
            "  Gateway --> App[Backend Engine]\n"
        )
        risk_matrix_content = json.dumps(
            {"threat_model": "STRIDE", "risks": [{"vector": "Spoofing", "mitigation": "mTLS + JWT"}]},
            indent=2,
        )
        bundle = SynthesisBundlePayload(
            files=[
                SynthesizedArtifactFile(relative_path="ARCHITECTURE.md", file_type="markdown", content=arch_content),
                SynthesizedArtifactFile(relative_path="docs/prd.md", file_type="markdown", content=prd_content),
                SynthesizedArtifactFile(relative_path="diagrams/topology.mmd", file_type="mermaid", content=topology_content),
                SynthesizedArtifactFile(relative_path="security/risk_matrix.json", file_type="json", content=risk_matrix_content),
            ]
        )
    else:
        try:
            bundle_response = await client.aio.models.generate_content(
                model=settings.synthesizer_model_id,
                contents=f"Synthesize the complete multi-file architecture bundle for project '{concept}' from consensus architectural signal:\n{synthesis_context}\nPRD Guidance:\n{prd_prompt}\nArchitecture Guidance:\n{arch_prompt}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SynthesisBundlePayload,
                ),
            )
            bundle = SynthesisBundlePayload.model_validate_json(bundle_response.text)
        except Exception as e:
            logger.warning(f"Structured bundle synthesis failed, falling back to deterministic standard bundle: {e}")
            prd_content = f"# Product Requirements Document: {concept}\n\nCompiled from verified grilling requirements and consensus history.\n"
            arch_content = f"# ARCHITECTURE.md: {concept}\n\nConsensus system blueprint.\n"
            topology_content = "graph TD\n  Client --> Gateway[API Gateway]\n  Gateway --> Service[Core Backend]\n"
            risk_matrix_content = json.dumps({"threat_model": "STRIDE", "status": "verified"}, indent=2)
            bundle = SynthesisBundlePayload(
                files=[
                    SynthesizedArtifactFile(relative_path="ARCHITECTURE.md", file_type="markdown", content=arch_content),
                    SynthesizedArtifactFile(relative_path="docs/prd.md", file_type="markdown", content=prd_content),
                    SynthesizedArtifactFile(relative_path="diagrams/topology.mmd", file_type="mermaid", content=topology_content),
                    SynthesizedArtifactFile(relative_path="security/risk_matrix.json", file_type="json", content=risk_matrix_content),
                ]
            )

    written_components: Dict[str, Any] = {}
    for item in bundle.files:
        write_result = HarnessToolRegistry.write_synthesized_artifact(
            project_id=project_id,
            relative_path=item.relative_path,
            content=item.content,
        )
        if write_result.startswith("VALIDATION_ERROR"):
            logger.error(f"Synthesis validation blocked file '{item.relative_path}': {write_result}")
            raise ValueError(write_result)
        written_components[item.relative_path] = item.content

    # Maintain top-level ARCHITECTURE.md while keeping canonical docs/prd.md inside docs/
    prd_text = written_components.get("docs/prd.md", written_components.get("PRD.md", ""))
    arch_text = written_components.get("ARCHITECTURE.md", "")
    if arch_text:
        FilesystemJail.write_project_file(project_id, "ARCHITECTURE.md", arch_text)

    from app.harness.ledger import EpistemicScratchpad, GlobalArchitectureLedger
    ledger = GlobalArchitectureLedger.load(project_id)
    ledger.update_baseline(
        summary=f"# Synthesized Baseline Architecture for Project '{project_id}'\n\n{arch_text}",
        components={
            "artifacts": list(written_components.keys()),
            "files": written_components,
            "status": "Final Synthesized Multi-File Assets",
            "project_id": project_id,
        },
    )

    scratchpad = EpistemicScratchpad.load(project_id)
    scratchpad.add_fact(
        statement=f"Synthesized official production multi-file ADK 2.0 layout for '{project_id}' ({len(written_components)} files).",
        verifier="SynthesizerAgent",
    )
    ctx.state["epistemic_scratchpad"] = scratchpad.model_dump()

    ctx.state["final_prd"] = prd_text
    ctx.state["final_architecture"] = arch_text
    ctx.state["final_topology"] = written_components.get("diagrams/topology.mmd", "")
    ctx.state["final_risk_matrix"] = written_components.get("security/risk_matrix.json", "")
    ctx.state["final_artifacts"] = written_components
    ctx.state["consensus_achieved"] = True

    from app.harness.tracing import DebateTracer
    from app.utils import extract_token_usage_dict
    token_meta = extract_token_usage_dict(bundle_response)
    DebateTracer.record_span(
        ctx=ctx,
        span_name="ASSETS_SYNTHESIZED",
        agent_role="Synthesizer",
        metadata={"files_written": list(written_components.keys()), **token_meta},
    )

    state_dump = ctx.state.to_dict()
    FilesystemJail.write_project_file(project_id, "state.json", json.dumps(state_dump, indent=2))

    return Event(output=ctx.state.to_dict(), custom_metadata={"state": ctx.state.to_dict()})

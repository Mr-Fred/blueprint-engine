import json
import logging
from pathlib import Path
from typing import Any, Dict

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


def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()


@node
async def synthesis_node(ctx: Context, node_input: Any) -> Event:
    """Node 5: Compiles the final PRD.md and ARCHITECTURE.md from debate history and writes them safely."""
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept", "")

    current_round = ctx.state.get("current_round", 1)
    rounds_count = current_round - 1
    history_text = ""

    for i in range(1, rounds_count + 1):
        try:
            round_data = FilesystemJail.read_project_file(project_id, f"round_{i}.json")
            r = json.loads(round_data)
            history_text += (
                f"\n--- Round {r.get('round_number')} Scores: {r.get('scores')} ---\n"
                f"PROPOSAL:\n{r.get('proposal_draft')}\n\nCRITIQUE:\n{r.get('critique')}\n"
            )
        except Exception as e:
            logger.debug(f"Could not load round_{i}.json for synthesis: {e}")

    skills_dir = Path(__file__).parent / "skills"
    matched_skills = load_matching_skills(skills_dir, f"{concept} {history_text}")

    prd_prompt = get_prd_synthesis_prompt(concept, history_text, matched_skills)
    arch_prompt = get_architecture_synthesis_prompt(concept, history_text, matched_skills)

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
    else:
        try:
            prd_response = await client.aio.interactions.create(model=settings.synthesizer_model_id, input=prd_prompt)
            prd_content = prd_response.steps[-1].content[0].text
        except Exception as e:
            logger.warning(f"Interactions failed for PRD synthesis, falling back: {e}")
            prd_response = await client.aio.models.generate_content(model=settings.synthesizer_model_id, contents=prd_prompt)
            prd_content = prd_response.text

        try:
            arch_response = await client.aio.interactions.create(model=settings.synthesizer_model_id, input=arch_prompt)
            arch_content = arch_response.steps[-1].content[0].text
        except Exception as e:
            logger.warning(f"Interactions failed for ARCHITECTURE synthesis, falling back: {e}")
            arch_response = await client.aio.models.generate_content(model=settings.synthesizer_model_id, contents=arch_prompt)
            arch_content = arch_response.text

    FilesystemJail.write_project_file(project_id, "PRD.md", prd_content)
    FilesystemJail.write_project_file(project_id, "ARCHITECTURE.md", arch_content)

    ctx.state["final_prd"] = "[Saved to PRD.md]"
    ctx.state["final_architecture"] = "[Saved to ARCHITECTURE.md]"
    ctx.state["consensus_achieved"] = True

    state_dump = ctx.state.to_dict()
    FilesystemJail.write_project_file(project_id, "state.json", json.dumps(state_dump, indent=2))

    return Event(output=ctx.state.to_dict(), custom_metadata={"state": ctx.state.to_dict()})

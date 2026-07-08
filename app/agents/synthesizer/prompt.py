import pathlib
from typing import Optional


def get_prd_synthesis_prompt(concept: str, history_text: str, skills_context: Optional[str] = None) -> str:
    """Constructs the prompt for synthesizing the final rigorous Product Requirements Document (PRD)."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"

    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Lead Documentation Synthesizer."

    prompt = f"""{guidelines}

---

Synthesize the final, rigorous Product Requirements Document (PRD) for the concept: "{concept}"
using the following architectural debate history and resolutions:
{history_text}"""

    if skills_context:
        prompt += f"\n\n--- DOCUMENTATION & PRD STANDARDS ---\nFollow these loaded domain standards:\n{skills_context}"

    prompt += """

Include:
1. Goal Description
2. Target Persona & Use Cases
3. Complete functional requirements
4. Non-Functional constraints
5. A numbered, horizontal implementation TASKLIST."""
    return prompt


def get_architecture_synthesis_prompt(concept: str, history_text: str, skills_context: Optional[str] = None) -> str:
    """Constructs the prompt for synthesizing the final production-ready ARCHITECTURE.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"

    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Lead Documentation Synthesizer."

    prompt = f"""{guidelines}

---

Synthesize the final, production-ready ARCHITECTURE.md for the concept: "{concept}"
using the following architectural debate history and resolutions:
{history_text}"""

    if skills_context:
        prompt += f"\n\n--- ARCHITECTURAL & DIAGRAM STANDARDS ---\nFollow these loaded architectural paradigms:\n{skills_context}"

    prompt += """

Include:
1. Hexagonal / Clean Architecture diagram description
2. Database schema & scaling topology
3. Security & IAM model
4. SRE & Observability SLOs
5. API definitions."""
    return prompt

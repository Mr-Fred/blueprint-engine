import pathlib
from typing import Optional


def get_judge_evaluation_prompt(proposal: str, combined_critiques: str, skills_context: Optional[str] = None) -> str:
    """Constructs the prompt for the Independent Master Architect Judge by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"

    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Independent Master Architect Judge."

    prompt = f"""{guidelines}

---

Evaluate the following proposed design against its security and SRE critiques.

Proposed Design:
{proposal}

Critiques & Audits:
{combined_critiques}"""

    if skills_context:
        prompt += f"\n\n--- ARCHITECTURAL & EVALUATION STANDARDS ---\nUse the following loaded design paradigms and standards during your scoring assessment:\n{skills_context}"

    prompt += (
        "\n\n--- EPISTEMIC SCRATCHPAD VERIFICATION ---\n"
        "MANDATORY INSTRUCTION: Call `query_verified_facts(project_id)` to verify all locked project requirements "
        "and architectural facts. If the proposal violates or regresses on any verified fact, penalize the corresponding quality pillar scores below 0.85.\n\n"
        "Assign a score between 0.0 (failing/flawed) and 1.0 (perfectly ready) for the 6 software quality pillars."
    )
    return prompt

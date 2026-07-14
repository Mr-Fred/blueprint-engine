import pathlib
from typing import Any, Dict, List, Optional


def get_judge_evaluation_prompt(
    proposal: str,
    combined_critiques: str,
    skills_context: Optional[str] = None,
    rounds_history: Optional[List[Any]] = None,
    open_blockers: Optional[List[Any]] = None,
) -> str:
    """Constructs the prompt for the Independent Master Architect Judge by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"

    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Independent Master Architect Judge."

    delta_card_block = ""
    if rounds_history or open_blockers:
        score_lines = []
        if rounds_history:
            for rnd in rounds_history:
                rnd_num = rnd.get("round_number", "?") if isinstance(rnd, dict) else getattr(rnd, "round_number", "?")
                scores = rnd.get("scores", {}) if isinstance(rnd, dict) else getattr(rnd, "scores", {})
                if hasattr(scores, "model_dump"):
                    scores = scores.model_dump()
                elif not isinstance(scores, dict):
                    scores = {}
                score_lines.append(
                    f"Round {rnd_num} -> P:{scores.get('performance', 0):.2f} S:{scores.get('scalability', 0):.2f} "
                    f"Sec:{scores.get('security', 0):.2f} Rel:{scores.get('reliability', 0):.2f} "
                    f"M:{scores.get('maintainability', 0):.2f} Cost:{scores.get('cost_efficiency', 0):.2f}"
                )

        blocker_lines = []
        if open_blockers:
            for item in open_blockers:
                item_dict = item.model_dump() if hasattr(item, "model_dump") else (item if isinstance(item, dict) else {})
                if item_dict:
                    category = item_dict.get("category", "BLOCKER")
                    title = item_dict.get("threat_title") or item_dict.get("gap_title") or item_dict.get("title", "Unresolved Issue")
                    component = item_dict.get("component", "System")
                    blocker_lines.append(f"- [{category}] {title} (Target: {component})")

        delta_card_block = "\n\n--- DELTA EVALUATION CARD (MONOTONIC SCORING PROTOCOL) ---\n"
        if score_lines:
            delta_card_block += "Historical Score Trajectory:\n" + "\n".join(score_lines) + "\n\n"
        if blocker_lines:
            delta_card_block += "Active Unresolved Blockers (status='OPEN'):\n" + "\n".join(blocker_lines) + "\n\n"
        delta_card_block += (
            "IMPORTANT JUDGE MANDATE: Do NOT score the proposal from scratch. Instead, check whether the new proposal explicitly "
            "resolves the Active Unresolved Blockers above. If resolved, increase scores monotonically relative to the previous round. "
            "If blockers remain unresolved or new regressions are introduced, hold or lower the scores accordingly."
        )

    prompt = f"""{guidelines}

---

Evaluate the following proposed design against its security and SRE critiques.

Proposed Design:
{proposal}

Critiques & Audits:
{combined_critiques}{delta_card_block}"""

    if skills_context:
        prompt += f"\n\n--- ARCHITECTURAL & EVALUATION STANDARDS ---\nUse the following loaded design paradigms and standards during your scoring assessment:\n{skills_context}"

    prompt += (
        "\n\n--- EPISTEMIC SCRATCHPAD VERIFICATION ---\n"
        "MANDATORY INSTRUCTION: Call `query_verified_facts(project_id)` to verify all locked project requirements "
        "and architectural facts. If the proposal violates or regresses on any verified fact, penalize the corresponding quality pillar scores below 0.85.\n\n"
        "Assign a score between 0.0 (failing/flawed) and 1.0 (perfectly ready) for the 6 software quality pillars."
    )
    return prompt

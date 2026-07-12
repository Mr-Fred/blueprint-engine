import pathlib


def get_performance_prompt(concept: str, current_round: int, history: list, judge_directive: str = None, skills_context: str = None) -> str:
    """Constructs the prompt for the Lead Performance & Scaling Architect by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"

    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Lead Performance & Scaling Architect."

    prompt = f"""{guidelines}

---

Your objective is to propose a high-performance, robust, and scalable software design blueprint for the following concept:
"{concept}"

Current Round: {current_round}"""

    if history:
        last_round = history[-1]
        prompt += (
            f"\n\n--- PREVIOUS ROUND PROPOSAL ---\n{last_round.get('proposal_draft', '')}"
            f"\n\n--- AUDITORS' STEP-BY-STEP HARDENING & CRITIQUE ---\n{last_round.get('critique', '')}"
            "\n\nCRITICAL AUDIT REMEDIATION REQUIREMENT:\n"
            "You MUST systematically apply and address every step-by-step hardening instruction "
            "provided above by the Security and SRE auditors. Explicitly describe how your refined "
            "blueprint incorporates their required safeguards, circuit breakers, IAM controls, and observability SLOs."
        )

    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize addressing this judge feedback in your refined design proposal with highest precedence."

    if skills_context:
        prompt += f"\n\n--- DOMAIN SKILLS & ARCHITECTURAL PATTERNS ---\nUse the following loaded skills and design paradigms to formulate a scalable, robust architecture:\n{skills_context}"

    prompt += "\n\nProvide your detailed architectural proposal focusing on: Paradigm (OOP/FP), Data storage, API contracts, scaling limits, and throughput."
    return prompt

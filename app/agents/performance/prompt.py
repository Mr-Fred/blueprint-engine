import pathlib


def get_performance_prompt(concept: str, current_round: int, history: list, judge_directive: str = None, skills_context: str = None, project_id: str = None) -> str:
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
        prev_proposal = getattr(last_round, "proposal_draft", None) or (last_round.get("proposal_draft", "") if isinstance(last_round, dict) else "")
        prev_critique = getattr(last_round, "critique", None) or (last_round.get("critique", "") if isinstance(last_round, dict) else "")
        prompt += (
            f"\n\n--- PREVIOUS ROUND PROPOSAL DIGEST ---\n{prev_proposal}"
            f"\n\n--- AUDITORS' HARDENING & CRITIQUE DIGEST ---\n{prev_critique}"
            "\n\nSTATE HYGIENE & AUDIT REMEDIATION REQUIREMENT:\n"
            "Do NOT repeat verbose intermediate draft markdown. Address the auditors' required safeguards, "
            "circuit breakers, and architectural trade-offs directly, building upon atomic Epistemic Scratchpad facts."
        )


    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize addressing this judge feedback in your refined design proposal with highest precedence."

    if skills_context:
        prompt += f"\n\n--- DOMAIN SKILLS & ARCHITECTURAL PATTERNS ---\nUse the following loaded skills and design paradigms to formulate a scalable, robust architecture:\n{skills_context}"

    facts_block = ""
    if project_id:
        try:
            from app.harness.tools import HarnessToolRegistry
            facts = HarnessToolRegistry.query_verified_facts(project_id)
            if facts:
                lines = [f"- [{f.get('verifier', 'System')}]: {f.get('statement')}" for f in facts]
                facts_block = "\n\n--- CURRENT VERIFIED EPISTEMIC FACTS (EPISTEMIC SCRATCHPAD) ---\n" + "\n".join(lines)
        except Exception:
            pass

    prompt += (
        f"{facts_block}\n\n--- EPISTEMIC SCRATCHPAD & FACT VERIFICATION ---\n"
        "You MUST adhere to all verified epistemic facts listed above. Do not propose any technology that contradicts locked facts.\n"
        "If you establish a new foundational architectural discovery or requirement, explicitly document it under an '### Epistemic Discoveries' section.\n\n"
        "Provide your detailed architectural proposal focusing on: Paradigm (OOP/FP), Data storage, API contracts, scaling limits, and throughput."
    )
    return prompt

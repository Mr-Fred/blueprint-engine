import pathlib
from app.utils import truncate_prompt_text

def get_sre_prompt(proposal: str, judge_directive: str = None, skills_context: str = None, project_id: str = None) -> str:
    """Constructs the prompt for the Site Reliability Engineer by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"
    
    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Expert Site Reliability Engineer (SRE)."

    truncated_proposal = truncate_prompt_text(proposal, max_chars=4000)
    prompt = f"""{guidelines}

---

Critique the following architectural proposal draft:

"{truncated_proposal}"


Provide your SRE review focusing STRICTLY on:
1. Reliability, high availability, failover, and disaster recovery.
2. Observability, telemetry, logging, and CI/CD operations.
3. Capacity planning, auto-scaling, and infrastructure automation."""

    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize auditing the proposal against this judge feedback."

    if skills_context:
        prompt += f"\n\n--- DOMAIN SKILLS & RELIABILITY PATTERNS ---\nUse the following loaded skills to formulate concrete observability, resilience, and DevOps prescriptions:\n{skills_context}"

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
        f"{facts_block}\n\n--- EPISTEMIC SCRATCHPAD & RELIABILITY REQUIREMENTS ---\n"
        "You MUST ensure the proposal complies with all verified facts above.\n"
        "If you establish a new non-negotiable SRE constraint or mitigation rule, explicitly document it under an '### Epistemic Discoveries' section.\n\n"
        "CRITICAL HARDENING REQUIREMENT:\n"
        "In your `detailed_critique`, you MUST explicitly formulate clear, numbered, step-by-step SRE hardening "
        "and resilience instructions (e.g., circuit breaker configs, retry policies, SLO definitions) "
        "so the Lead Architect knows exactly what to add or modify in the next debate round."
    )
    return prompt

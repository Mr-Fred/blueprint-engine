import pathlib

def get_sre_prompt(proposal: str, judge_directive: str = None, skills_context: str = None) -> str:
    """Constructs the prompt for the Site Reliability Engineer by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"
    
    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Site Reliability Engineer (SRE)."

    prompt = f"""{guidelines}

---

Critique the following architectural proposal draft:

"{proposal}"

Provide your SRE review focusing STRICTLY on:
1. Reliability, high availability, failover, and disaster recovery.
2. Observability (SLIs/SLOs, logging, tracing, monitoring) and CI/CD operations.
3. Capacity planning, auto-scaling, and infrastructure automation."""

    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize auditing the proposal's compliance with this judge feedback."

    if skills_context:
        prompt += f"\n\n--- DOMAIN SKILLS & RELIABILITY PATTERNS ---\nUse the following loaded skills to formulate concrete observability, resilience, and DevOps prescriptions:\n{skills_context}"

    prompt += (
        "\n\nCRITICAL HARDENING REQUIREMENT:\n"
        "In your `detailed_critique`, you MUST explicitly formulate clear, numbered, step-by-step SRE hardening "
        "and resilience instructions (e.g., circuit breaker configs, retry policies, SLO definitions) "
        "so the Lead Architect knows exactly what to add or modify in the next debate round."
    )
    return prompt

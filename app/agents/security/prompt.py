import pathlib

def get_security_prompt(proposal: str, judge_directive: str = None) -> str:
    """Constructs the prompt for the Security & Resilience Auditor by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"
    
    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Expert Security & Resilience Auditor."

    prompt = f"""{guidelines}

---

Critique the following architectural proposal draft:

"{proposal}"

Provide your security review focusing STRICTLY on:
1. Identity & Access Management (IAM), OAuth, and Session Security.
2. Resilience, high availability, failover, and rate limiting.
3. Input sanitization and OWASP Top 10 mitigation."""

    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize auditing the proposal's compliance with this judge feedback."

    return prompt

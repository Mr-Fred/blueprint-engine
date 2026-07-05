import pathlib

def get_security_prompt(proposal: str, judge_directive: str = None, skills_context: str = None) -> str:
    """Constructs the prompt for the Security & Resilience Auditor by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"
    
    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Expert Security Auditor."

    prompt = f"""{guidelines}

---

Critique the following architectural proposal draft:

"{proposal}"

Provide your security review focusing STRICTLY on:
1. Identity & Access Management (IAM), OAuth, and Session Security.
2. Threat modeling, data encryption (at rest and transit), and network isolation.
3. Input sanitization, OWASP Top 10 mitigation, and compliance (SOC2/GDPR)."""

    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize auditing the proposal's compliance with this judge feedback."

    if skills_context:
        prompt += f"\n\n--- DOMAIN SKILLS & MITIGATION PATTERNS ---\nUse the following loaded skills to formulate concrete mitigation plans for any identified vulnerabilities:\n{skills_context}"

    return prompt

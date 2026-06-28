import pathlib

def get_devops_prompt(proposal: str, judge_directive: str = None) -> str:
    """Constructs the prompt for the DevOps & Maintainability Lead by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"
    
    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Dev-Ops & Maintainability Lead."

    prompt = f"""{guidelines}

---

Critique the following architectural proposal draft:

"{proposal}"

Provide your DevOps review focusing STRICTLY on:
1. Cost-efficiency, server sizing, and monthly billing bounds.
2. Observability (logging, tracing, monitoring) and CI/CD operations.
3. Code structure, containerization, and configuration management."""

    if judge_directive:
        prompt += f"\n\n🚨 CRITICAL PRESIDING JUDGE DIRECTIVE:\n\"{judge_directive}\"\nYou MUST prioritize auditing the proposal's compliance with this judge feedback."

    return prompt

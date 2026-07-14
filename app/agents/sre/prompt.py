import pathlib
from typing import Any, Dict, List, Optional

def get_sre_prompt(
    proposal: str,
    judge_directive: str = None,
    skills_context: str = None,
    project_id: str = None,
    agreement_summary: str = None,
    previous_gaps: Optional[List[Any]] = None,
) -> str:
    """Constructs the prompt for the Site Reliability Engineer by dynamically loading guidelines from AGENT.md."""
    agent_dir = pathlib.Path(__file__).parent
    agent_md_path = agent_dir / "AGENT.md"
    
    if agent_md_path.exists():
        guidelines = agent_md_path.read_text(encoding="utf-8")
    else:
        guidelines = "You are the Expert Site Reliability Engineer (SRE)."

    prompt = f"""{guidelines}

---

Critique the following architectural proposal draft:

"{proposal}"


Provide your SRE review focusing STRICTLY on:
1. Reliability, high availability, failover, and disaster recovery.
2. Observability, telemetry, logging, and CI/CD operations.
3. Capacity planning, auto-scaling, and infrastructure automation."""

    if agreement_summary:
        prompt += (
            f"\n\n--- ESTABLISHED ARCHITECTURAL AGREEMENT MATRIX ---\n"
            "STATE HYGIENE MANDATE: Do NOT repeat intermediate draft markdown or re-litigate agreed baseline points below unless a new reliability gap is introduced:\n"
            f"{agreement_summary}"
        )

    if previous_gaps:
        gap_lines = []
        for g in previous_gaps:
            g_dict = g.model_dump() if hasattr(g, "model_dump") else (g if isinstance(g, dict) else {})
            if g_dict:
                gap_lines.append(
                    f"- [{g_dict.get('category', 'SRE_GAP')}] {g_dict.get('gap_title', '')} "
                    f"(Target: {g_dict.get('component', '')}, Previous Status: {g_dict.get('status', 'OPEN')})"
                )
        if gap_lines:
            prompt += (
                "\n\n--- PREVIOUS ROUND SRE RELIABILITY GAP LEDGER ---\n"
                + "\n".join(gap_lines)
                + "\nIMPORTANT AUDITOR MANDATE: For each SRE gap listed above, check whether the new proposal draft explicitly resolves it. "
                "In your `sre_gap_register`, explicitly set `status='RESOLVED'` if remediated (citing proof in `remediation_status`) or keep `status='OPEN'` if unmitigated."
            )

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
        "In your `sre_gap_register` (`remediation_status`) and your `detailed_critique`, you MUST explicitly formulate clear, numbered, step-by-step SRE hardening "
        "and resilience instructions (e.g., circuit breaker configs, retry policies, SLO definitions) "
        "so the Lead Architect knows exactly what to add or modify in the next debate round."
    )
    return prompt

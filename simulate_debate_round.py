import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from app.config import settings
from app.agents.performance.agent import performance_agent_node
from app.agents.security.agent import security_agent_node
from app.agents.sre.agent import sre_agent_node
from app.agents.judge.agent import evaluate_and_score_node
from app.types import DebateRoundEnvelope

class MockState(dict):
    def to_dict(self):
        return dict(self)

async def simulate_debate():
    settings.mock_mode = True
    print("=" * 80)
    print("         MULTI-AGENT DEBATE HARNESS SIMULATION (MOCK MODE)         ")
    print("=" * 80)

    # Initialize Context
    state = MockState({
        "project_id": "sim_proj_001",
        "concept": "High-Throughput Global Financial Transactions API",
        "current_round": 1,
        "rounds_history": []
    })
    ctx = SimpleNamespace(state=state)

    report_lines = []
    report_lines.append("# Multi-Agent Debate Harness: 2-Round Simulation Trace\n")
    report_lines.append(f"**Project Concept**: `{ctx.state['concept']}`\n")
    report_lines.append(f"**Execution Mode**: `Mock / Deterministic`\n")

    print("\n[INIT] Concept:", ctx.state["concept"])
    print("-" * 80)

    # -------------------------------------------------------------------------
    # ROUND 1
    # -------------------------------------------------------------------------
    print("\n======================= ROUND 1: INITIAL DEBATE =======================")
    report_lines.append("## Round 1: Initial Architectural Proposal & Domain Audits\n")

    # 1. Performance Lead Architect
    print("\n>>> [AGENT 1: PERFORMANCE LEAD ARCHITECT]")
    perf_events = [e async for e in performance_agent_node._func(ctx, {})]
    perf_output = perf_events[-1].output
    proposal_text = perf_output["proposal"] if isinstance(perf_output, dict) else getattr(perf_output, "proposal", "")
    print("  [OUTPUT] Proposal Preview:\n   ", proposal_text[:250].replace("\n", " ") + "...")
    report_lines.append("### 1. Performance Lead Architect\n")
    report_lines.append("**Input**:\n- `concept`: High-Throughput Global Financial Transactions API\n- `current_round`: 1\n")
    report_lines.append(f"**Output Proposal**:\n```markdown\n{proposal_text.strip()}\n```\n")

    # 2. Security Auditor
    print("\n>>> [AGENT 2: SECURITY AUDITOR]")
    sec_events = [e async for e in security_agent_node._func(ctx, perf_output)]
    sec_output = sec_events[-1].output
    sec_critique = (sec_output.get("security_rubric", {}) if isinstance(sec_output, dict) else {}).get("detailed_critique") or (sec_output["security_critique"] if isinstance(sec_output, dict) else getattr(sec_output, "security_critique", ""))
    print("  [OUTPUT] Security Critique Preview:\n   ", sec_critique[:200].replace("\n", " ") + "...")
    print("  [OUTPUT] Security STRIDE Threat Register Items Generated:")
    stride_reg = []
    if isinstance(sec_output, dict) and "security_rubric" in sec_output:
        rub = sec_output["security_rubric"]
        stride_reg = rub.get("stride_threat_register", []) if isinstance(rub, dict) else getattr(rub, "stride_threat_register", [])
        for threat in stride_reg:
            cat = threat.get("category") if isinstance(threat, dict) else getattr(threat, "category", "")
            title = threat.get("threat_title") if isinstance(threat, dict) else getattr(threat, "threat_title", "")
            stat = threat.get("status") if isinstance(threat, dict) else getattr(threat, "status", "OPEN")
            print(f"           - [{cat}] {title} (Status: {stat})")

    report_lines.append("### 2. Security Auditor\n")
    report_lines.append("**Input**:\n- Round 1 Architectural Blueprint\n")
    report_lines.append(f"**Output Critique**:\n```markdown\n{sec_critique.strip()}\n```\n")
    report_lines.append("**STRIDE Threat Register Output**:\n| Category | Threat Title | Component | Severity | Status |\n|---|---|---|---|---|\n")
    for t in stride_reg:
        cat = t.get("category") if isinstance(t, dict) else getattr(t, "category", "")
        title = t.get("threat_title") if isinstance(t, dict) else getattr(t, "threat_title", "")
        comp = t.get("component") if isinstance(t, dict) else getattr(t, "component", "")
        sev = t.get("severity") if isinstance(t, dict) else getattr(t, "severity", "")
        stat = t.get("status") if isinstance(t, dict) else getattr(t, "status", "OPEN")
        report_lines.append(f"| `{cat}` | {title} | `{comp}` | `{sev}` | **{stat}** |\n")

    # 3. SRE Auditor
    print("\n>>> [AGENT 3: SRE AUDITOR]")
    sre_events = [e async for e in sre_agent_node._func(ctx, perf_output)]
    sre_output = sre_events[-1].output
    sre_critique = (sre_output.get("sre_rubric", {}) if isinstance(sre_output, dict) else {}).get("detailed_critique") or (sre_output["sre_critique"] if isinstance(sre_output, dict) else getattr(sre_output, "sre_critique", ""))
    print("  [OUTPUT] SRE Critique Preview:\n   ", sre_critique[:200].replace("\n", " ") + "...")
    print("  [OUTPUT] SRE Reliability Gap Register Items Generated:")
    sre_reg = []
    if isinstance(sre_output, dict) and "sre_rubric" in sre_output:
        rub = sre_output["sre_rubric"]
        sre_reg = rub.get("sre_gap_register", []) if isinstance(rub, dict) else getattr(rub, "sre_gap_register", [])
    elif hasattr(sre_output, "sre_rubric") and sre_output.sre_rubric:
        sre_reg = sre_output.sre_rubric.sre_gap_register
    for gap in sre_reg:
        cat = gap.get("category") if isinstance(gap, dict) else getattr(gap, "category", "")
        title = gap.get("gap_title") if isinstance(gap, dict) else getattr(gap, "gap_title", "")
        stat = gap.get("status") if isinstance(gap, dict) else getattr(gap, "status", "OPEN")
        print(f"           - [{cat}] {title} (Status: {stat})")

    report_lines.append("\n### 3. Site Reliability Engineer (SRE Auditor)\n")
    report_lines.append("**Input**:\n- Round 1 Architectural Blueprint\n")
    report_lines.append(f"**Output Critique**:\n```markdown\n{sre_critique.strip()}\n```\n")
    report_lines.append("**SRE Reliability Gap Register Output**:\n| Category | Gap Title | Component | Severity | Status |\n|---|---|---|---|---|\n")
    for g in sre_reg:
        cat = g.get("category") if isinstance(g, dict) else getattr(g, "category", "")
        title = g.get("gap_title") if isinstance(g, dict) else getattr(g, "gap_title", "")
        comp = g.get("component") if isinstance(g, dict) else getattr(g, "component", "")
        sev = g.get("severity") if isinstance(g, dict) else getattr(g, "severity", "")
        stat = g.get("status") if isinstance(g, dict) else getattr(g, "status", "OPEN")
        report_lines.append(f"| `{cat}` | {title} | `{comp}` | `{sev}` | **{stat}** |\n")

    # 4. Master Architect Judge
    print("\n>>> [AGENT 4: MASTER ARCHITECT JUDGE]")
    judge_input = {
        "security_agent_node": sec_output,
        "sre_agent_node": sre_output,
    }
    judge_events = [e async for e in evaluate_and_score_node._func(ctx, judge_input)]
    history = ctx.state["rounds_history"]
    r1_scores = history[-1]["scores"]
    r1_scores_dict = r1_scores if isinstance(r1_scores, dict) else r1_scores.model_dump()
    print("  [OUTPUT] Round 1 Quality Pillar Scores:")
    for k, v in r1_scores_dict.items():
        print(f"           {k.ljust(16)}: {v:.2f}")

    report_lines.append("\n### 4. Presiding Master Architect Judge (Round 1)\n")
    report_lines.append("**Input Context**:\n- Round 1 Blueprint + Security STRIDE Threats + SRE Reliability Gaps\n")
    report_lines.append("**Quality Pillar Scores**:\n| Pillar | Score (Round 1) |\n|---|---|\n")
    for k, v in r1_scores_dict.items():
        report_lines.append(f"| `{k}` | **{v:.2f}** |\n")

    # -------------------------------------------------------------------------
    # ROUND 2
    # -------------------------------------------------------------------------
    ctx.state["current_round"] = 2
    print("\n================ ROUND 2: DELTA REFINEMENT & MITIGATION ================")
    report_lines.append("\n---\n## Round 2: Delta Evaluation & Hardening Refinement\n")

    perf_events_r2 = [e async for e in performance_agent_node._func(ctx, {})]
    perf_output_r2 = perf_events_r2[-1].output

    sec_events_r2 = [e async for e in security_agent_node._func(ctx, perf_output_r2)]
    sec_output_r2 = sec_events_r2[-1].output

    sre_events_r2 = [e async for e in sre_agent_node._func(ctx, perf_output_r2)]
    sre_output_r2 = sre_events_r2[-1].output

    judge_input_r2 = {
        "security_agent_node": sec_output_r2,
        "sre_agent_node": sre_output_r2,
    }
    judge_events_r2 = [e async for e in evaluate_and_score_node._func(ctx, judge_input_r2)]
    r2_scores = ctx.state["rounds_history"][-1]["scores"]
    r2_scores_dict = r2_scores if isinstance(r2_scores, dict) else r2_scores.model_dump()

    print("  [OUTPUT] Round 2 Quality Pillar Scores (Monotonic Progress):")
    report_lines.append("\n### Presiding Master Architect Judge (Round 2 Delta Assessment)\n")
    report_lines.append("**Input Context**:\n- Round 2 Blueprint + Delta Evaluation Card (Unresolved OPEN Blockers from Round 1)\n")
    report_lines.append("**Quality Pillar Scores & Delta Comparison**:\n| Pillar | Round 1 | Round 2 | Delta Trajectory |\n|---|---|---|---|\n")

    for k in r1_scores_dict.keys():
        s1 = r1_scores_dict[k]
        s2 = r2_scores_dict[k]
        diff = s2 - s1
        diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"
        print(f"           {k.ljust(16)}: {s2:.2f} (Delta: {diff_str})")
        report_lines.append(f"| `{k}` | {s1:.2f} | **{s2:.2f}** | `{diff_str}` |\n")

    artifact_dir = Path("C:/Users/Fred/.gemini/antigravity-ide/brain/f785e370-4e1e-4774-a0b8-40262bae09ea")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    trace_path = artifact_dir / "simulation_trace.md"
    trace_path.write_text("".join(report_lines), encoding="utf-8")

    print("\n" + "=" * 80)
    print("             SIMULATION COMPLETED SUCCESSFULLY!                      ")
    print(f"   Saved trace report to: {trace_path}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(simulate_debate())

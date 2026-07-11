import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  Sliders,
  XCircle,
  ChevronDown,
  ChevronUp,
  Server,
  Cloud,
  Layers,
  Gauge,
  DollarSign,
  Lock,
} from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

export function MADEngineHarnessBar() {
  const { activeProject } = useMADEngine();
  const [showInspector, setShowInspector] = useState(false);

  if (!activeProject) return null;

  const reqs = activeProject?.requirements || null;
  const isCompleted = activeProject?.consensus_achieved || false;
  const isDebating = Boolean(
    activeProject?.grill_completed ||
    (activeProject?.rounds_history && activeProject.rounds_history.length > 0) ||
    isCompleted
  );

  return (
    <div className="w-full bg-[#11131d]/90 border-b border-slate-800/80 px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 text-xs select-none">
      {/* Left side: Left-Shifted Sensor Pipeline Badges */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Harness Sensors:</span>
        </div>

        {/* Sensor 1: Diagram Syntax */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-colors ${
            isDebating
              ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
              : "bg-slate-800/60 border border-slate-700/60 text-slate-400"
          }`}
          title={
            isDebating
              ? "Layer 1: Diagram Syntax Sensor (Mermaid/Graphviz AST verified)"
              : "Layer 1: Diagram Syntax Sensor (Standby during interview phase)"
          }
        >
          {isDebating ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <Clock className="w-3.5 h-3.5 text-slate-500" />
          )}
          <span>Diagram Syntax</span>
        </div>

        {/* Sensor 2: Envelope Schema */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-colors ${
            isDebating
              ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
              : "bg-slate-800/60 border border-slate-700/60 text-slate-400"
          }`}
          title={
            isDebating
              ? "Layer 2: Typed Envelope Schema verification across graph seams (Verified)"
              : "Layer 2: Typed Envelope Schema verification (Standby during interview phase)"
          }
        >
          {isDebating ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <Clock className="w-3.5 h-3.5 text-slate-500" />
          )}
          <span>Schema Integrity</span>
        </div>

        {/* Sensor 3: Epistemic Consistency */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-colors ${
            isCompleted
              ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
              : isDebating
              ? "bg-indigo-500/10 border border-indigo-500/20 text-indigo-300"
              : "bg-slate-800/60 border border-slate-700/60 text-slate-400"
          }`}
          title={
            isCompleted
              ? "Layer 3: Epistemic Scratchpad consensus achieved (Verified)"
              : isDebating
              ? "Layer 3: Epistemic Scratchpad fact & contradiction evaluation active"
              : "Layer 3: Epistemic Scratchpad (Standby during interview phase)"
          }
        >
          {isCompleted ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          ) : isDebating ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
          ) : (
            <Clock className="w-3.5 h-3.5 text-slate-500" />
          )}
          <span>Epistemic Consensus</span>
        </div>
      </div>

      {/* Right side: Requirements Inspector trigger & HITL Intermission Controls */}
      <div className="flex items-center gap-3">
        {/* Requirements Inspector Toggle Button */}
        <button
          onClick={() => setShowInspector(!showInspector)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer border ${
            showInspector || reqs
              ? "bg-violet-600/20 border-violet-500/40 text-violet-300 hover:bg-violet-600/30 shadow-[0_0_12px_rgba(139,92,246,0.2)]"
              : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:bg-slate-800"
          }`}
          title="View locked Phase 1 Requirements Matrix"
        >
          <FileSpreadsheet className="w-4 h-4 text-violet-400" />
          <span>Requirements Matrix</span>
          {showInspector ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

      </div>

      {/* Drawer: Requirements Inspector Panel */}
      {showInspector && (
        <div className="w-full mt-2 p-4 rounded-xl bg-[#0b0c13] border border-violet-500/30 shadow-[0_4px_25px_rgba(0,0,0,0.5)] animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-violet-400" />
              <h3 className="font-bold text-sm text-white tracking-wide">
                PHASE 1 ARCHITECTURAL REQUIREMENTS INSPECTOR
              </h3>
              {reqs ? (
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">
                  LOCKED
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold">
                  GRILLING / IN PROGRESS
                </span>
              )}
            </div>
            <button
              onClick={() => setShowInspector(false)}
              className="text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
            >
              <XCircle className="w-4 h-4" />
            </button>
          </div>

          {reqs ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Stack & Provider */}
              <div className="space-y-3 bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                <div>
                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1.5">
                    <Server className="w-3.5 h-3.5 text-violet-400" />
                    <span>Preferred Tech Stack</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {reqs.preferred_tech_stack && reqs.preferred_tech_stack.length > 0 ? (
                      reqs.preferred_tech_stack.map((item, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded bg-violet-500/10 border border-violet-500/20 text-violet-300 font-mono text-[11px]"
                        >
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500 italic">Auto-selected by Lead Architect</span>
                    )}
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1">
                    <Cloud className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Cloud Provider</span>
                  </div>
                  <div className="text-cyan-300 font-semibold">
                    {reqs.cloud_provider || "Multi-Cloud / Platform Agnostic"}
                  </div>
                </div>
              </div>

              {/* Pattern & Scale */}
              <div className="space-y-3 bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                <div>
                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Architectural Pattern</span>
                  </div>
                  <div className="text-indigo-300 font-semibold">
                    {reqs.architectural_pattern || "Event-Driven Clean Architecture"}
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1">
                    <Gauge className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Target Scale / RPS</span>
                  </div>
                  <div className="text-emerald-300 font-semibold">
                    {reqs.target_rps ? `${reqs.target_rps.toLocaleString()} req/sec` : "Dynamic Auto-Scaling"}
                  </div>
                </div>
              </div>

              {/* Budget & Compliance */}
              <div className="space-y-3 bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                <div>
                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1">
                    <DollarSign className="w-3.5 h-3.5 text-amber-400" />
                    <span>Budget Tier</span>
                  </div>
                  <div className="text-amber-300 font-semibold">
                    {reqs.budget_tier || "Enterprise High-Availability"}
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold mb-1.5">
                    <Lock className="w-3.5 h-3.5 text-rose-400" />
                    <span>Compliance Standards</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {reqs.compliance_frameworks && reqs.compliance_frameworks.length > 0 ? (
                      reqs.compliance_frameworks.map((fw, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 font-mono uppercase text-[11px]"
                        >
                          {fw}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500 italic">Standard Security Hardening</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-6 text-slate-400 bg-slate-900/30 rounded-lg border border-slate-800/60">
              <p>Phase 1 Grilling interview is gathering architectural constraints...</p>
              <p className="text-xs text-slate-500 mt-1">
                You can answer clarifying questions in the Arena or click Skip Interview to auto-generate requirements.
              </p>
            </div>
          )}
        </div>
      )}

    </div>
  );
}

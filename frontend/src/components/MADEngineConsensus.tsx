import React from "react";
import { Activity, Cpu, Layers, Shield, Zap, Code, DollarSign, AlertCircle } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

const getScoreColor = (score: number) => {
  if (score >= 0.85) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (score >= 0.6) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/30";
  return "text-rose-400 bg-rose-500/10 border-rose-500/30";
};

const getScoreBgBar = (score: number) => {
  if (score >= 0.85) return "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]";
  if (score >= 0.6) return "bg-yellow-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]";
  return "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]";
};

export function MADEngineConsensus() {
  const { activeProject } = useMADEngine();

  return (
    <div className="bg-[#0d0e15]/80 border border-slate-800/80 rounded-2xl p-5 flex flex-col gap-5 shadow-xl backdrop-blur-sm">
      <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
        <Activity className="w-4 h-4 text-indigo-400" /> Consensus Dashboard
      </h2>
      {!activeProject || activeProject.rounds_history.length === 0 ? (
        <div className="text-center p-6 bg-slate-900/30 border border-slate-800/50 rounded-xl flex flex-col items-center justify-center">
          <AlertCircle className="w-8 h-8 text-slate-600 mb-2" />
          <p className="text-[11px] text-slate-500">Wait for Round 1 evaluation to compute quality metrics</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Visual Circle Meter */}
          <div className="flex items-center justify-center p-2">
            <div className="relative flex items-center justify-center">
              <svg className="w-24 h-24 transform -rotate-90">
                <circle
                  cx="48"
                  cy="48"
                  r="40"
                  className="stroke-slate-800"
                  strokeWidth="6"
                  fill="transparent"
                />
                <circle
                  cx="48"
                  cy="48"
                  r="40"
                  className={activeProject.consensus_achieved ? "stroke-emerald-500" : "stroke-indigo-500"}
                  strokeWidth="6"
                  fill="transparent"
                  strokeDasharray={251.2}
                  strokeDashoffset={251.2 - (251.2 * (activeProject.consensus_achieved ? 1.0 : 0.70))}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute flex flex-col items-center justify-center text-center">
                <span className="text-[10px] text-slate-500 uppercase font-bold tracking-tight">Status</span>
                <span className="text-xs font-bold text-white uppercase tracking-tight">
                  {activeProject.consensus_achieved ? "Verified" : "Debating"}
                </span>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Pillar Metrics (Threshold ≥ 0.85)</span>
            
            {/* Render 6 Pillar Bars from Latest Round */}
            {Object.entries(activeProject.rounds_history[activeProject.rounds_history.length - 1].scores).map(([pillar, val]) => (
              <div key={pillar} className="space-y-1">
                <div className="flex justify-between items-center text-xs">
                  <span className="capitalize text-slate-300 flex items-center gap-1.5">
                    {pillar === "performance" && <Cpu className="w-3 h-3 text-emerald-400" />}
                    {pillar === "scalability" && <Layers className="w-3 h-3 text-cyan-400" />}
                    {pillar === "security" && <Shield className="w-3 h-3 text-rose-400" />}
                    {pillar === "reliability" && <Zap className="w-3 h-3 text-yellow-400" />}
                    {pillar === "maintainability" && <Code className="w-3 h-3 text-violet-400" />}
                    {pillar === "cost_efficiency" && <DollarSign className="w-3 h-3 text-amber-400" />}
                    {pillar.replace("_", " ")}
                  </span>
                  <span className={`font-mono font-bold px-2 py-0.5 rounded border text-[10px] ${getScoreColor(val)}`}>
                    {val.toFixed(2)}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${getScoreBgBar(val)}`}
                    style={{ width: `${val * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

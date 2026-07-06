import React from "react";
import { Activity, Cpu, Layers, Shield, Zap, Code, DollarSign, AlertCircle, Target, CheckCircle2, Award } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

const getScoreColor = (score: number) => {
  if (score >= 0.85) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (score >= 0.6) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/30";
  return "text-rose-400 bg-rose-500/10 border-rose-500/30";
};

const getScoreBgBar = (score: number) => {
  if (score >= 0.85) return "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_12px_rgba(16,185,129,0.5)]";
  if (score >= 0.6) return "bg-gradient-to-r from-yellow-500 to-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.5)]";
  return "bg-gradient-to-r from-rose-500 to-pink-500 shadow-[0_0_12px_rgba(244,63,94,0.5)]";
};

export function MADEngineConsensus() {
  const { activeProject } = useMADEngine();

  const latestRound = activeProject?.rounds_history && activeProject.rounds_history.length > 0
    ? activeProject.rounds_history[activeProject.rounds_history.length - 1]
    : null;

  const scores = latestRound ? Object.values(latestRound.scores) : [];
  const avgScore = scores.length > 0
    ? scores.reduce((acc, val) => acc + val, 0) / scores.length
    : 0;

  const progress = Math.min(Math.max(avgScore, 0), 1.0);
  const strokeDashoffset = 251.2 - (251.2 * progress);

  return (
    <div className="bg-[#0d0e15]/90 border border-slate-800/80 rounded-2xl p-5 flex flex-col gap-5 shadow-2xl backdrop-blur-md transition-all">
      <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
        <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-400 animate-pulse" /> Consensus Dashboard
        </h2>
        {latestRound && (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
            TURN {latestRound.round_number}
          </span>
        )}
      </div>

      {!activeProject || !latestRound ? (
        <div className="text-center p-6 bg-slate-900/40 border border-slate-800/60 rounded-xl flex flex-col items-center justify-center my-4">
          <Target className="w-8 h-8 text-slate-600 mb-2 animate-bounce" />
          <h4 className="text-xs font-bold text-slate-400 mb-1">Awaiting Evaluation</h4>
          <p className="text-[11px] text-slate-500 max-w-[220px] leading-relaxed">
            Quality metrics will compute automatically once Round 1 architectural debate concludes.
          </p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {/* Visual Dynamic Circle Gauge */}
          <div className="flex items-center justify-center p-2.5 bg-slate-900/50 border border-slate-800/60 rounded-xl relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/5 via-transparent to-emerald-500/5 pointer-events-none" />
            
            <div className="flex items-center gap-5 z-10">
              <div className="relative flex items-center justify-center">
                <svg className="w-20 h-20 transform -rotate-90">
                  <circle
                    cx="40"
                    cy="40"
                    r="34"
                    className="stroke-slate-800"
                    strokeWidth="6"
                    fill="transparent"
                  />
                  <circle
                    cx="40"
                    cy="40"
                    r="34"
                    className={activeProject.consensus_achieved ? "stroke-emerald-400" : avgScore >= 0.7 ? "stroke-indigo-400" : "stroke-amber-400"}
                    strokeWidth="6"
                    fill="transparent"
                    strokeDasharray={213.6}
                    strokeDashoffset={213.6 - (213.6 * Math.min(avgScore, 1))}
                    strokeLinecap="round"
                    style={{ transition: "stroke-dashoffset 1s ease-in-out" }}
                  />
                </svg>
                <div className="absolute flex flex-col items-center justify-center text-center">
                  <span className="text-[9px] text-slate-400 font-medium uppercase tracking-tight">Quality</span>
                  <span className={`text-xs font-black font-mono tracking-tight ${avgScore >= 0.85 ? "text-emerald-400" : "text-white"}`}>
                    {(avgScore * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-1 border-l border-slate-800/80 pl-4 py-0.5">
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide">
                  {activeProject.consensus_achieved ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Consensus Met</span>
                    </>
                  ) : (
                    <>
                      <Award className="w-3.5 h-3.5 text-amber-400" />
                      <span className="text-amber-400">In Review</span>
                    </>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 leading-tight">
                  Target Threshold: <span className="font-mono text-slate-200 font-bold">85%</span>
                </p>
                <p className="text-[10px] text-slate-500 leading-tight">
                  {activeProject.consensus_achieved ? "All 6 pillars verified." : "Iterating towards target quality."}
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              6-Pillar Metric Breakdown
            </span>
            
            {/* Render 6 Pillar Bars from Latest Round in a 2-Column Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(latestRound.scores).map(([pillar, val]) => (
                <div key={pillar} className="p-2 bg-slate-900/40 border border-slate-800/50 rounded-xl space-y-1 transition hover:border-slate-700/60 shadow-sm">
                  <div className="flex justify-between items-center text-[11px]">
                    <span className="capitalize text-slate-300 font-medium flex items-center gap-1.5">
                      {pillar === "performance" && <Cpu className="w-3.5 h-3.5 text-emerald-400" />}
                      {pillar === "scalability" && <Layers className="w-3.5 h-3.5 text-cyan-400" />}
                      {pillar === "security" && <Shield className="w-3.5 h-3.5 text-rose-400" />}
                      {pillar === "reliability" && <Zap className="w-3.5 h-3.5 text-yellow-400" />}
                      {pillar === "maintainability" && <Code className="w-3.5 h-3.5 text-violet-400" />}
                      {pillar === "cost_efficiency" && <DollarSign className="w-3.5 h-3.5 text-amber-400" />}
                      {pillar.replace("_", " ")}
                    </span>
                    <span className={`font-mono font-bold px-1.5 py-0.5 rounded border text-[10px] ${getScoreColor(val)}`}>
                      {val.toFixed(2)}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800/60">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${getScoreBgBar(val)}`}
                      style={{ width: `${Math.min(val * 100, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


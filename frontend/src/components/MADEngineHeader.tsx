import React from "react";
import { Cpu, Activity, CheckCircle, Zap } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

export function MADEngineHeader() {
  const { activeProject, isStreaming, cavemanMode, toggleCavemanMode } = useMADEngine();

  return (
    <header className="border-b border-slate-800/60 bg-[#0d0e15]/70 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex justify-between items-center">
      <div className="flex items-center gap-3">
        <div className="p-2.5 bg-gradient-to-tr from-violet-600 to-indigo-600 rounded-xl shadow-[0_0_15px_rgba(99,102,241,0.4)] flex items-center justify-center">
          <Cpu className="w-6 h-6 text-white animate-pulse" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            MAD ENGINE <span className="text-xs bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full font-semibold border border-indigo-500/30">v2.0 Beta</span>
          </h1>
          <p className="text-xs text-slate-400">Multi-Agent Self-Correcting Software Architect Debate</p>
        </div>
      </div>
      
      {/* Streaming Status & Caveman Toggle Indicator */}
      <div className="flex items-center gap-4">
        {/* Caveman Mode Toggle */}
        <button
          onClick={() => toggleCavemanMode()}
          className={`text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-2 border transition-all cursor-pointer ${
            cavemanMode
              ? "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.2)]"
              : "bg-slate-800/40 border-slate-700/50 text-slate-400 hover:bg-slate-800/60"
          }`}
          title="Toggle Caveman Mode (concise responses, ~75% token saving)"
        >
          <Zap className={`w-3.5 h-3.5 ${cavemanMode ? "fill-amber-400 text-amber-400 animate-pulse" : "text-slate-500"}`} />
          <span>CAVEMAN MODE: {cavemanMode ? "ON" : "OFF"}</span>
        </button>

        {activeProject ? (
          <div className="text-xs font-mono text-slate-400 bg-slate-800/40 border border-slate-700/50 px-3 py-1.5 rounded-lg flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,1)]"></span>
            ID: <span className="text-indigo-300 font-semibold">{activeProject.project_id}</span>
          </div>
        ) : null}
        {isStreaming ? (
          <div className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 animate-spin" />
            <span>DEBATE ACTIVE</span>
          </div>
        ) : activeProject?.consensus_achieved ? (
          <div className="text-xs font-semibold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-3 py-1.5 rounded-lg flex items-center gap-2">
            <CheckCircle className="w-3.5 h-3.5 text-indigo-400" />
            <span>CONSENSUS ACHIEVED</span>
          </div>
        ) : (
          <div className="text-xs font-semibold text-slate-400 bg-slate-800/40 border border-slate-700/50 px-3 py-1.5 rounded-lg flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-slate-500"></span>
            <span>STANDBY</span>
          </div>
        )}
      </div>
    </header>
  );
}

import React from "react";
import { Zap, Play, AlertCircle } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

const SUGGESTED_CONCEPTS = [
  "High-throughput collaborative design whiteboard with canvas synchronization",
  "Jailed serverless microservices runtime executing untrusted sandboxed code",
  "Real-time fraud prevention engine with sub-10ms transactional latency limits"
];

export function MADEngineLauncher() {
  const { conceptInput, setConceptInput, isStreaming, handleStartDebate, streamError } = useMADEngine();

  return (
    <div className="bg-[#0d0e15]/80 border border-slate-800/80 rounded-2xl p-5 flex flex-col gap-4 shadow-xl backdrop-blur-sm">
      <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
        <Zap className="w-4 h-4 text-indigo-400" /> Launcher
      </h2>
      <p className="text-xs text-slate-400 leading-relaxed">
        Input a software product idea. Three specialized AI architects will debate and score design tradeoffs.
      </p>
      
      <div className="flex flex-col gap-2">
        <textarea
          value={conceptInput}
          onChange={(e) => setConceptInput(e.target.value)}
          placeholder="Describe your system concept (e.g. Build an end-to-end encrypted messaging engine...)"
          rows={4}
          className="w-full text-xs bg-slate-900/60 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 rounded-xl p-3 text-slate-100 placeholder:text-slate-500 outline-none transition resize-none leading-relaxed"
          disabled={isStreaming}
        />
        
        <button
          onClick={() => handleStartDebate(conceptInput)}
          disabled={isStreaming || !conceptInput.trim()}
          className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed rounded-xl text-xs font-semibold text-white transition flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/10 cursor-pointer"
        >
          <Play className="w-3.5 h-3.5" /> Start Architect Debate
        </button>
      </div>

      {streamError ? (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl flex items-start gap-2 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{streamError}</span>
        </div>
      ) : null}

      {/* Quick-start Suggestions */}
      <div className="mt-2">
        <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-2">Suggestions</span>
        <div className="flex flex-col gap-1.5">
          {SUGGESTED_CONCEPTS.map((concept, i) => (
            <button
              key={i}
              onClick={() => setConceptInput(concept)}
              disabled={isStreaming}
              className="text-left text-[11px] text-slate-400 bg-slate-900/30 hover:bg-slate-800/40 border border-slate-800/60 p-2 rounded-lg leading-snug transition"
            >
              {concept}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

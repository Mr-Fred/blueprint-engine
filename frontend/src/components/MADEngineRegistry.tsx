import React from "react";
import { Layers, Terminal, Trash2, CheckCircle2, Activity, FolderGit2, Sparkles } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

export function MADEngineRegistry() {
  const { projectsList, activeProject, isStreaming, fetchProjectState, handleDeleteProject } = useMADEngine();

  return (
    <div className="bg-[#0d0e15]/90 border border-slate-800/80 rounded-2xl p-5 flex-1 flex flex-col gap-4 shadow-2xl backdrop-blur-md min-h-[220px] transition-all">
      <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
        <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" /> Active Registry
        </h2>
        <span className="text-[10px] font-mono bg-slate-800/80 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700/80 font-bold">
          {projectsList.length} {projectsList.length === 1 ? "Session" : "Sessions"}
        </span>
      </div>
      
      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-2.5 h-full">
        {projectsList.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800/80 rounded-xl bg-slate-900/30 my-2">
            <FolderGit2 className="w-9 h-9 text-slate-600 mb-2 animate-pulse" />
            <span className="text-xs font-bold text-slate-300 mb-0.5">No Active Projects</span>
            <p className="text-[11px] text-slate-500 max-w-[200px] leading-relaxed">
              Use the launcher above to initiate a new multi-agent architecture debate session.
            </p>
          </div>
        ) : (
          projectsList.map((p, idx) => {
            const isActive = activeProject?.project_id === p.project_id;
            const isCompleted =
              p.status === "completed" ||
              p.consensus_achieved ||
              Boolean(p.final_prd) ||
              Boolean(p.final_architecture) ||
              (isActive &&
                Boolean(
                  activeProject?.consensus_achieved ||
                    activeProject?.final_prd ||
                    activeProject?.final_architecture
                ));

            return (
              <div
                key={idx}
                role="button"
                tabIndex={0}
                onClick={() => {
                  if (!isStreaming) {
                    fetchProjectState(p.project_id);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isStreaming) {
                    fetchProjectState(p.project_id);
                  }
                }}
                className={`text-left p-3.5 rounded-xl border transition-all duration-200 group relative cursor-pointer shadow-sm ${
                  isActive
                    ? "bg-gradient-to-r from-indigo-950/60 to-slate-900/80 border-indigo-500/60 border-l-4 border-l-indigo-500 shadow-indigo-500/10 shadow-md"
                    : "bg-slate-900/40 border-slate-800/60 hover:bg-slate-800/50 hover:border-slate-700/80"
                } ${isStreaming ? "opacity-50 pointer-events-none" : ""}`}
              >
                <div className="flex justify-between items-center mb-1.5 pr-7">
                  <div className="flex items-center gap-1.5">
                    <Terminal className={`w-3.5 h-3.5 ${isActive ? "text-indigo-400" : "text-slate-500"}`} />
                    <span className={`text-[11px] font-mono font-extrabold uppercase tracking-tight ${isActive ? "text-white" : "text-indigo-400"}`}>
                      {p.project_id}
                    </span>
                  </div>

                  {/* Status Badge */}
                  {isCompleted ? (
                    <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-md">
                      <CheckCircle2 className="w-2.5 h-2.5 shrink-0" /> Done
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2 py-0.5 rounded-md animate-pulse">
                      <Activity className="w-2.5 h-2.5 shrink-0" /> Active
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed font-sans">{p.concept}</p>
                
                <button
                  onClick={(e) => handleDeleteProject(p.project_id, e)}
                  className="absolute top-2.5 right-2.5 p-1.5 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 opacity-0 group-hover:opacity-100 hover:bg-rose-500 hover:text-white transition-all duration-150 cursor-pointer z-10 shadow-sm"
                  title="Delete Session from Disk"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}


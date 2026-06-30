import React from "react";
import { Layers, Terminal, Trash2 } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

export function MADEngineRegistry() {
  const { projectsList, activeProject, isStreaming, fetchProjectState, handleDeleteProject } = useMADEngine();

  return (
    <div className="bg-[#0d0e15]/80 border border-slate-800/80 rounded-2xl p-5 flex-1 flex flex-col gap-4 shadow-xl backdrop-blur-sm min-h-[200px]">
      <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
        <Layers className="w-4 h-4 text-indigo-400" /> Active Registry
      </h2>
      
      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-2 h-full">
        {projectsList.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-4">
            <Terminal className="w-8 h-8 text-slate-600 mb-2" />
            <p className="text-[11px] text-slate-500">No active projects found in this session registry</p>
          </div>
        ) : (
          projectsList.map((p, idx) => (
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
              className={`text-left p-3 rounded-xl border transition group relative cursor-pointer ${
                activeProject?.project_id === p.project_id
                  ? "bg-indigo-500/10 border-indigo-500/40"
                  : "bg-slate-900/30 border-slate-800/50 hover:bg-slate-800/30"
              } ${isStreaming ? 'opacity-50 pointer-events-none' : ''}`}
            >
              <div className="flex justify-between items-center mb-1 pr-6">
                <span className="text-[10px] font-mono font-bold text-indigo-400 uppercase tracking-tight">{p.project_id}</span>
                <span className="text-[10px] text-slate-500">
                  {p.status === "completed" ? "Completed" : "Active"}
                </span>
              </div>
              <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">{p.concept}</p>
              
              <button
                onClick={(e) => handleDeleteProject(p.project_id, e)}
                className="absolute top-2 right-2 p-1.5 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 opacity-0 group-hover:opacity-100 hover:bg-rose-500/20 transition cursor-pointer z-10"
                title="Delete Project"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Clipboard, Check } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

export function MADEngineBlueprints() {
  const { activeProject } = useMADEngine();
  const [activeDocTab, setActiveDocTab] = useState<"prd" | "architecture">("prd");
  const [copied, setCopied] = useState(false);

  // Copy document markdown to clipboard
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-[#0d0e15]/80 border border-slate-800/80 rounded-2xl p-5 flex-1 flex flex-col gap-4 shadow-xl backdrop-blur-sm min-h-[250px]">
      <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
        <FileText className="w-4 h-4 text-indigo-400" /> Compiled Blueprints
      </h2>
      {!activeProject || (!activeProject.final_prd && !activeProject.final_architecture) ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800 rounded-xl">
          <FileText className="w-10 h-10 text-slate-700 mb-2 animate-pulse" />
          <h4 className="text-xs font-semibold text-slate-400 mb-0.5">Documents Not Compiled Yet</h4>
          <p className="text-[10px] text-slate-500 max-w-[200px]">
            Achieve ≥ 0.85 scores or click &quot;Force Compilation&quot; to trigger markdown document generation.
          </p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-3 min-h-[200px]">
          
          {/* Tabs to select active doc */}
          <div className="flex border-b border-slate-800">
            <button
              onClick={() => setActiveDocTab("prd")}
              className={`flex-1 py-2 text-xs font-bold transition-all border-b-2 ${
                activeDocTab === "prd"
                  ? "text-indigo-400 border-indigo-500"
                  : "text-slate-500 border-transparent hover:text-slate-400"
              }`}
            >
              Product Requirements (PRD)
            </button>
            <button
              onClick={() => setActiveDocTab("architecture")}
              className={`flex-1 py-2 text-xs font-bold transition-all border-b-2 ${
                activeDocTab === "architecture"
                  ? "text-indigo-400 border-indigo-500"
                  : "text-slate-500 border-transparent hover:text-slate-400"
              }`}
            >
              System Architecture
            </button>
          </div>

          {/* Display active doc contents safely */}
          <div className="flex-1 bg-slate-950/70 border border-slate-900 rounded-xl p-4 overflow-y-auto relative">
            
            {/* Copy Button */}
            <button
              onClick={() => handleCopy(activeDocTab === "prd" ? activeProject.final_prd || "" : activeProject.final_architecture || "")}
              className="absolute top-2 right-2 p-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 hover:text-white transition cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Clipboard className="w-3.5 h-3.5" />}
            </button>
            
            <div className="space-y-4 prose prose-invert prose-sm max-w-none">
              {activeDocTab === "prd"
                ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeProject.final_prd || ""}</ReactMarkdown>
                : <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeProject.final_architecture || ""}</ReactMarkdown>}
            </div>
          </div>
          
          {/* Path indicator */}
          <div className="text-[10px] font-mono text-slate-500 bg-slate-950/40 p-2 border border-slate-900 rounded-lg flex items-center justify-between">
            <span>File Target:</span>
            <span className="text-indigo-400 font-semibold">
              outputs/{activeProject.project_id}/{activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Clipboard, Check, Download, RefreshCw, Terminal, BookOpen, Layers, Sparkles } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

const blueprintMarkdownComponents: any = {
  code({ node, inline, className, children, ...props }: any) {
    const isMultiLine = String(children).includes("\n");
    const isInline = inline || (!isMultiLine && !className);
    return isInline ? (
      <code className="bg-slate-900/90 text-indigo-300 font-mono text-[11px] px-1.5 py-0.5 rounded border border-slate-800/80 inline" {...props}>
        {children}
      </code>
    ) : (
      <div className="my-3 rounded-xl overflow-hidden border border-slate-800/80 bg-slate-950/90 shadow-lg block">
        <div className="bg-slate-900/90 px-3.5 py-1.5 border-b border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400 font-mono">
          <span className="flex items-center gap-1.5 text-indigo-400 font-bold">
            <Terminal className="w-3 h-3" /> Technical Specification Snippet
          </span>
          <span className="text-[9px] text-slate-500 uppercase tracking-wider">Markdown Code</span>
        </div>
        <pre className="p-3.5 overflow-x-auto text-[11px] font-mono leading-relaxed text-slate-200">
          <code {...props}>{children}</code>
        </pre>
      </div>
    );
  },
  table: ({ children }: any) => (
    <div className="overflow-x-auto my-3 rounded-xl border border-slate-800/80 shadow-md block">
      <table className="w-full text-left border-collapse text-xs font-sans">{children}</table>
    </div>
  ),
  th: ({ children }: any) => <th className="bg-slate-900/90 p-2.5 font-bold text-slate-200 border-b border-slate-800/80 text-[11px] uppercase tracking-wider">{children}</th>,
  td: ({ children }: any) => <td className="p-2.5 border-b border-slate-800/50 text-slate-300 text-xs font-sans">{children}</td>,
  blockquote: ({ children }: any) => <blockquote className="border-l-4 border-indigo-500/80 bg-gradient-to-r from-indigo-950/40 to-slate-900/40 pl-4 py-2.5 my-3 rounded-r-xl text-xs text-indigo-200/90 italic font-sans">{children}</blockquote>,
  ul: ({ children }: any) => <ul className="list-disc pl-5 my-2 space-y-1.5 text-xs text-slate-300 font-sans">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal pl-5 my-2 space-y-1.5 text-xs text-slate-300 font-sans">{children}</ol>,
  li: ({ children }: any) => <li className="leading-relaxed pl-1 text-slate-300">{children}</li>,
  h1: ({ children }: any) => <h1 className="text-base font-extrabold text-white mt-5 mb-2.5 border-b border-slate-800/80 pb-2 flex items-center gap-2 font-sans tracking-tight">{children}</h1>,
  h2: ({ children }: any) => <h2 className="text-xs font-bold text-indigo-300 mt-4 mb-2 uppercase tracking-wider font-sans">{children}</h2>,
  h3: ({ children }: any) => <h3 className="text-[11px] font-bold text-slate-200 mt-3.5 mb-1.5 font-sans">{children}</h3>,
  h4: ({ children }: any) => <h4 className="text-[11px] font-semibold text-slate-300 mt-2.5 mb-1 font-sans">{children}</h4>,
  p: ({ children }: any) => <div className="text-xs leading-relaxed my-2 text-slate-300 font-sans">{children}</div>,
  strong: ({ children }: any) => <strong className="font-bold text-indigo-300">{children}</strong>,
  em: ({ children }: any) => <em className="italic text-indigo-200/90">{children}</em>,
};

export function MADEngineBlueprints() {
  const { activeProject, fetchProjectState } = useMADEngine();
  const [activeDocTab, setActiveDocTab] = useState<"prd" | "architecture">("prd");
  const [copied, setCopied] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Copy document markdown to clipboard
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Download document as .md file
  const handleDownload = (text: string, filename: string) => {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleRefresh = async () => {
    if (!activeProject) return;
    setIsRefreshing(true);
    await fetchProjectState(activeProject.project_id);
    setIsRefreshing(false);
  };

  const currentContent = activeDocTab === "prd" ? activeProject?.final_prd : activeProject?.final_architecture;
  const isPlaceholder = currentContent === "[Saved to PRD.md]" || currentContent === "[Saved to ARCHITECTURE.md]";

  return (
    <div className="bg-[#0d0e15]/90 border border-slate-800/80 rounded-2xl p-5 flex-1 flex flex-col gap-4 shadow-2xl backdrop-blur-md min-h-[320px] transition-all">
      <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
        <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-indigo-400 animate-pulse" /> Compiled Blueprints
        </h2>
        {activeProject && (
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1 text-[10px] bg-slate-800/80 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700 transition cursor-pointer font-bold shadow-sm"
            title="Reload latest compiled specification from disk"
          >
            <RefreshCw className={`w-3 h-3 text-indigo-400 ${isRefreshing ? "animate-spin" : ""}`} /> Refresh
          </button>
        )}
      </div>

      {!activeProject || (!activeProject.final_prd && !activeProject.final_architecture) ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800/80 rounded-xl bg-slate-900/30 my-4">
          <Layers className="w-10 h-10 text-slate-600 mb-2.5 animate-bounce" />
          <h4 className="text-xs font-bold text-slate-300 mb-1">Specifications Inactive</h4>
          <p className="text-[11px] text-slate-500 max-w-[240px] leading-relaxed">
            Achieve target consensus (≥ 85%) or trigger asset synthesis during debate to compile production-ready markdown blueprints.
          </p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-3 min-h-[260px]">
          {/* Top Document Bar: Tabs + Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between bg-slate-900/80 border border-slate-800/80 rounded-xl p-1.5 gap-2 backdrop-blur-sm">
            {/* Tabs */}
            <div className="flex gap-1 flex-1">
              <button
                onClick={() => setActiveDocTab("prd")}
                className={`flex-1 py-1.5 px-3 text-xs font-bold transition-all rounded-lg flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeDocTab === "prd"
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <FileText className="w-3.5 h-3.5" /> Product Specs (PRD.md)
              </button>
              <button
                onClick={() => setActiveDocTab("architecture")}
                className={`flex-1 py-1.5 px-3 text-xs font-bold transition-all rounded-lg flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeDocTab === "architecture"
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Terminal className="w-3.5 h-3.5" /> Architecture (ARCHITECTURE.md)
              </button>
            </div>

            {/* Action Buttons Toolbar */}
            {currentContent && !isPlaceholder && (
              <div className="flex items-center gap-1.5 shrink-0 px-1 justify-end">
                <button
                  onClick={() => handleCopy(currentContent)}
                  className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/80 rounded-lg text-[10px] font-bold text-slate-300 hover:text-white transition flex items-center gap-1 cursor-pointer shadow-sm"
                  title="Copy markdown content to clipboard"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Clipboard className="w-3 h-3 text-indigo-400" />}
                  {copied ? "Copied!" : "Copy"}
                </button>
                <button
                  onClick={() => handleDownload(currentContent, activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md")}
                  className="px-2.5 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-lg text-[10px] font-bold text-white transition flex items-center gap-1 cursor-pointer shadow-sm"
                  title="Download raw markdown file"
                >
                  <Download className="w-3 h-3" /> Download .md
                </button>
              </div>
            )}
          </div>

          {/* Display active doc contents safely */}
          <div className="flex-1 bg-slate-950/90 border border-slate-800/80 rounded-xl p-6 overflow-y-auto relative shadow-inner max-h-[500px]">
            {isPlaceholder ? (
              <div className="flex flex-col items-center justify-center text-center p-8 my-4 bg-indigo-950/20 border border-indigo-500/30 rounded-xl">
                <Sparkles className="w-8 h-8 text-indigo-400 mb-2 animate-pulse" />
                <h4 className="text-xs font-bold text-white mb-1">Specification Written to Disk</h4>
                <p className="text-[11px] text-slate-400 max-w-[280px] mb-4">
                  The compilation engine saved {activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md"} to the local filesystem. Click refresh to load the full markdown view.
                </p>
                <button
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition flex items-center gap-1.5 shadow-md shadow-indigo-600/30 cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} /> Reload Document From Disk
                </button>
              </div>
            ) : (
              <div className="space-y-3 font-sans text-slate-300">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={blueprintMarkdownComponents}>
                  {currentContent || "_No content generated._"}
                </ReactMarkdown>
              </div>
            )}
          </div>
          
          {/* Path indicator */}
          <div className="text-[10px] font-mono text-slate-400 bg-slate-900/60 p-2.5 border border-slate-800/80 rounded-xl flex items-center justify-between">
            <span className="text-slate-500 uppercase tracking-wider font-bold">Disk Storage Target:</span>
            <span className="text-indigo-300 font-semibold bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
              outputs/{activeProject.project_id}/{activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}



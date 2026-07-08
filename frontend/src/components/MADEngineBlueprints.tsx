import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Clipboard, Check, Download, RefreshCw, Terminal, BookOpen, Layers, Sparkles, Maximize2, Minimize2, X, ExternalLink, Eye, ArrowLeft } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

const cleanMarkdown = (text?: string | null) => {
  if (!text) return "";
  let cleaned = text.trim();
  const fenceRegex = /^```(?:markdown|md|)\s*\n([\s\S]*?)\n```\s*$/i;
  const match = cleaned.match(fenceRegex);
  if (match) {
    return match[1].trim();
  }
  if (cleaned.startsWith("```") && cleaned.endsWith("```")) {
    const lines = cleaned.split("\n");
    lines.shift();
    if (lines[lines.length - 1].trim() === "```") lines.pop();
    return lines.join("\n").trim();
  }
  return cleaned;
};

const blueprintMarkdownComponents: any = {
  code({ node, inline, className, children, ...props }: any) {
    const isMultiLine = String(children).includes("\n");
    const isInline = inline || (!isMultiLine && !className);
    return isInline ? (
      <code className="bg-slate-900/90 text-indigo-300 font-mono text-[11px] px-1.5 py-0.5 rounded border border-slate-800/80 inline break-words" {...props}>
        {children}
      </code>
    ) : (
      <div className="my-3 rounded-xl overflow-hidden border border-slate-800/80 bg-slate-950/90 shadow-lg block max-w-full">
        <div className="bg-slate-900/90 px-3.5 py-1.5 border-b border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400 font-mono">
          <span className="flex items-center gap-1.5 text-indigo-400 font-bold">
            <Terminal className="w-3 h-3" /> Technical Specification Snippet
          </span>
          <span className="text-[9px] text-slate-500 uppercase tracking-wider">Markdown Code</span>
        </div>
        <pre className="p-3.5 overflow-x-auto max-w-full text-[11px] font-mono leading-relaxed text-slate-200 whitespace-pre">
          <code className="break-normal" {...props}>{children}</code>
        </pre>
      </div>
    );
  },
  table: ({ children }: any) => (
    <div className="overflow-x-auto max-w-full my-4 rounded-xl border border-slate-800/80 shadow-md block bg-slate-950/60">
      <table className="w-full text-left border-collapse text-xs sm:text-sm font-sans">{children}</table>
    </div>
  ),
  th: ({ children }: any) => <th className="bg-slate-900/90 p-3 font-bold text-slate-200 border-b border-slate-800/80 text-[11px] sm:text-xs uppercase tracking-wider whitespace-nowrap">{children}</th>,
  td: ({ children }: any) => <td className="p-3 border-b border-slate-800/50 text-slate-300 text-xs sm:text-sm font-sans max-w-[300px] sm:max-w-[450px] break-words">{children}</td>,
  blockquote: ({ children }: any) => <blockquote className="border-l-4 border-indigo-500/80 bg-gradient-to-r from-indigo-950/40 to-slate-900/40 pl-4 py-3 my-3 rounded-r-xl text-xs sm:text-sm text-indigo-200/90 italic font-sans break-words">{children}</blockquote>,
  ul: ({ children }: any) => <ul className="list-disc pl-6 my-2.5 space-y-1.5 text-xs sm:text-sm text-slate-300 font-sans break-words">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal pl-6 my-2.5 space-y-1.5 text-xs sm:text-sm text-slate-300 font-sans break-words">{children}</ol>,
  li: ({ children }: any) => <li className="leading-relaxed pl-1 text-slate-300">{children}</li>,
  h1: ({ children }: any) => <h1 className="text-lg sm:text-xl font-extrabold text-white mt-6 mb-3 border-b border-slate-800/80 pb-2.5 flex items-center gap-2 font-sans tracking-tight break-words">{children}</h1>,
  h2: ({ children }: any) => <h2 className="text-sm sm:text-base font-bold text-indigo-300 mt-5 mb-2.5 uppercase tracking-wider font-sans break-words">{children}</h2>,
  h3: ({ children }: any) => <h3 className="text-xs sm:text-sm font-bold text-slate-200 mt-4 mb-2 font-sans break-words">{children}</h3>,
  h4: ({ children }: any) => <h4 className="text-xs sm:text-sm font-semibold text-slate-300 mt-3 mb-1.5 font-sans break-words">{children}</h4>,
  p: ({ children }: any) => <div className="text-xs sm:text-sm leading-relaxed my-2.5 text-slate-300 font-sans break-words">{children}</div>,
  strong: ({ children }: any) => <strong className="font-bold text-indigo-300">{children}</strong>,
  em: ({ children }: any) => <em className="italic text-indigo-200/90">{children}</em>,
};

export function MADEngineBlueprints() {
  const { activeProject, fetchProjectState } = useMADEngine();
  const [activeDocTab, setActiveDocTab] = useState<"prd" | "architecture">("prd");
  const [copied, setCopied] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showInlinePreview, setShowInlinePreview] = useState(false);

  // Revert mechanism: press Esc key to close reader and return to dashboard
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isExpanded) {
        setIsExpanded(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isExpanded]);

  // Copy document markdown to clipboard
  const handleCopy = (text: string | null | undefined) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Download document as .md file
  const handleDownload = (text: string | null | undefined, filename: string) => {
    if (!text) return;
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
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-1 text-[10px] bg-slate-800/80 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700 transition cursor-pointer font-bold shadow-sm"
              title="Reload latest compiled specification from disk"
            >
              <RefreshCw className={`w-3 h-3 text-indigo-400 ${isRefreshing ? "animate-spin" : ""}`} /> Refresh
            </button>
            <button
              onClick={() => setIsExpanded(true)}
              className="flex items-center gap-1 text-[10px] bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 px-2.5 py-1 rounded-lg border border-indigo-500/30 transition cursor-pointer font-bold shadow-sm"
              title="Expand to Fullscreen Reader"
            >
              <Maximize2 className="w-3 h-3 text-indigo-400" /> Fullscreen
            </button>
          </div>
        )}
      </div>

      {!activeProject || (!activeProject.final_prd && !activeProject.final_architecture) ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-800/80 rounded-xl bg-slate-900/30 my-4 animate-in fade-in duration-300">
          <Layers className="w-10 h-10 text-slate-600 mb-2.5 animate-bounce" />
          <h4 className="text-xs font-bold text-slate-300 mb-1">Specifications Inactive</h4>
          <p className="text-[11px] text-slate-500 max-w-[240px] leading-relaxed">
            Achieve target consensus (≥ 85%) or trigger asset synthesis during debate to compile production-ready markdown blueprints.
          </p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-3 min-h-[220px] animate-in fade-in duration-300">
          {/* Interactive Pop-up Reader Banner */}
          <div className="bg-gradient-to-r from-indigo-950/40 via-slate-900/60 to-violet-950/40 border border-indigo-500/30 rounded-xl p-3 text-center shadow-md">
            <span className="text-[11px] font-bold text-indigo-300 flex items-center justify-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" /> Pop-up Overlay Reader Active
            </span>
            <p className="text-[10px] text-slate-400 mt-0.5">
              Blueprints & Mermaid diagrams open in a full-screen pop-up overlay for maximum clarity.
            </p>
          </div>

          {/* Interactive Specification Launcher Cards */}
          <div className="grid grid-cols-1 gap-2.5 flex-1">
            {/* PRD Launcher Card */}
            <div
              onClick={() => {
                setActiveDocTab("prd");
                setIsExpanded(true);
              }}
              className="group relative bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-indigo-500/50 rounded-xl p-3.5 transition-all duration-200 cursor-pointer shadow-md hover:shadow-lg hover:shadow-indigo-500/10 flex items-center justify-between overflow-hidden"
            >
              <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-indigo-500 to-violet-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
              <div className="flex items-center gap-3 min-w-0 pr-2">
                <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform duration-200">
                  <FileText className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-white group-hover:text-indigo-300 transition-colors truncate">Product Specification</h4>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full uppercase tracking-wider shrink-0">Ready</span>
                  </div>
                  <p className="text-[10px] text-slate-400 truncate mt-0.5">PRD.md • Features, metrics & target scope</p>
                </div>
              </div>
              <div className="w-7 h-7 rounded-lg bg-slate-800 group-hover:bg-indigo-600/20 border border-slate-700/60 group-hover:border-indigo-500/30 flex items-center justify-center shrink-0 transition-all duration-200 group-hover:translate-x-0.5">
                <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-400" />
              </div>
            </div>

            {/* Architecture Launcher Card */}
            <div
              onClick={() => {
                setActiveDocTab("architecture");
                setIsExpanded(true);
              }}
              className="group relative bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-indigo-500/50 rounded-xl p-3.5 transition-all duration-200 cursor-pointer shadow-md hover:shadow-lg hover:shadow-indigo-500/10 flex items-center justify-between overflow-hidden"
            >
              <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-violet-500 to-fuchsia-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
              <div className="flex items-center gap-3 min-w-0 pr-2">
                <div className="w-9 h-9 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform duration-200">
                  <Terminal className="w-4 h-4 text-violet-400" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-white group-hover:text-violet-300 transition-colors truncate">System Architecture</h4>
                    <span className="text-[9px] font-bold px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full uppercase tracking-wider shrink-0">Ready</span>
                  </div>
                  <p className="text-[10px] text-slate-400 truncate mt-0.5">ARCHITECTURE.md • 6-Pillar hexagonal & diagrams</p>
                </div>
              </div>
              <div className="w-7 h-7 rounded-lg bg-slate-800 group-hover:bg-violet-600/20 border border-slate-700/60 group-hover:border-violet-500/30 flex items-center justify-center shrink-0 transition-all duration-200 group-hover:translate-x-0.5">
                <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-violet-400" />
              </div>
            </div>
          </div>

          <button
            onClick={() => {
              setActiveDocTab("prd");
              setIsExpanded(true);
            }}
            className="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 hover:from-indigo-500 hover:via-indigo-400 hover:to-violet-500 text-white font-extrabold text-xs sm:text-sm uppercase tracking-wider rounded-xl shadow-xl shadow-indigo-600/30 hover:shadow-indigo-600/50 hover:scale-[1.01] active:scale-[0.99] transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer mt-2 border border-indigo-400/30"
          >
            <Maximize2 className="w-4 h-4 animate-pulse" /> View Full Specification
          </button>

          <button
            onClick={() => setShowInlinePreview(!showInlinePreview)}
            className="text-[10px] text-slate-400 hover:text-slate-200 underline transition cursor-pointer text-center pt-1"
          >
            {showInlinePreview ? "Hide Inline Markdown Preview" : "Show Inline Markdown Preview"}
          </button>

          {/* Optional Quick Peek Inline Reader */}
          {showInlinePreview && (
            <div className="flex flex-col gap-2 bg-slate-900/80 border border-slate-800/80 rounded-xl p-3 backdrop-blur-sm animate-in fade-in duration-200 mt-1 max-h-[350px] overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2 text-[10px] text-slate-400 font-mono">
                <span className="font-bold text-indigo-300 uppercase">{activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md"}</span>
                <button
                  onClick={() => handleCopy(currentContent)}
                  className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[9px] font-bold transition flex items-center gap-1"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Clipboard className="w-3 h-3 text-indigo-400" />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <div className="overflow-y-auto pr-1 space-y-2 font-sans text-slate-300">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={blueprintMarkdownComponents}>
                  {cleanMarkdown(currentContent) || "_No content generated._"}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fullscreen Pop-up Overlay Modal using React Portal to escape resizable panel containment */}
      {isExpanded && activeProject && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-[9999] bg-[#07080c]/98 backdrop-blur-3xl flex items-center justify-center p-2 sm:p-6 md:p-10 overflow-hidden animate-in fade-in duration-300 ease-out">
          <div className="max-w-[1400px] w-full h-[94vh] mx-auto flex flex-col bg-[#0d0e15] border border-slate-800/80 rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 ease-out">
            {/* Modal Top Bar - Sticky Header with Top-Left Back Button */}
            <div className="flex items-center justify-between px-6 py-4 bg-slate-900/95 border-b border-slate-800 shrink-0 sticky top-0 z-10 backdrop-blur-md">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setIsExpanded(false)}
                  className="px-3.5 py-1.5 bg-gradient-to-r from-slate-800 to-slate-800/80 hover:from-indigo-600 hover:to-violet-600 text-slate-200 hover:text-white rounded-xl text-xs font-extrabold transition-all duration-200 flex items-center gap-1.5 cursor-pointer border border-slate-700/80 hover:border-indigo-500 shadow-md group"
                  title="Return to main dashboard view (Or press Esc)"
                >
                  <ArrowLeft className="w-4 h-4 text-indigo-400 group-hover:text-white group-hover:-translate-x-0.5 transition-transform" /> Back to Dashboard
                </button>
                <div className="h-4 w-[1px] bg-slate-800 hidden sm:block" />
                <div className="flex items-center gap-2.5">
                  <BookOpen className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-sm sm:text-base font-extrabold text-white uppercase tracking-wider truncate max-w-[280px] sm:max-w-[500px]">
                    Specification Reader — <span className="text-indigo-400">{activeProject.concept}</span>
                  </h2>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm border border-slate-700/80"
                  title="Reload latest compiled specification from disk"
                >
                  <RefreshCw className={`w-3.5 h-3.5 text-indigo-400 ${isRefreshing ? "animate-spin" : ""}`} /> Reload Disk
                </button>
                <button
                  onClick={() => setIsExpanded(false)}
                  className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 rounded-xl text-xs font-extrabold transition flex items-center gap-1.5 cursor-pointer border border-rose-500/20 shadow-sm sm:hidden"
                >
                  <X className="w-4 h-4" /> Close
                </button>
              </div>
            </div>

            {/* Modal Document Tabs & Actions */}
            <div className="flex flex-wrap items-center justify-between bg-slate-950/80 px-6 py-3 border-b border-slate-800/80 gap-3 shrink-0">
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveDocTab("prd")}
                  className={`py-2 px-5 text-xs sm:text-sm font-bold transition-all rounded-xl flex items-center gap-2 cursor-pointer ${
                    activeDocTab === "prd"
                      ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 scale-[1.02]"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <FileText className="w-4 h-4" /> Product Specs (PRD.md)
                </button>
                <button
                  onClick={() => setActiveDocTab("architecture")}
                  className={`py-2 px-5 text-xs sm:text-sm font-bold transition-all rounded-xl flex items-center gap-2 cursor-pointer ${
                    activeDocTab === "architecture"
                      ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 scale-[1.02]"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <Terminal className="w-4 h-4" /> System Architecture (ARCHITECTURE.md)
                </button>
              </div>

              {currentContent && !isPlaceholder && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopy(currentContent)}
                    className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/80 rounded-xl text-xs font-bold text-slate-200 transition flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Clipboard className="w-4 h-4 text-indigo-400" />}
                    {copied ? "Copied to Clipboard!" : "Copy Markdown"}
                  </button>
                  <button
                    onClick={() => handleDownload(currentContent, activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md")}
                    className="px-3.5 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-xl text-xs font-bold text-white transition flex items-center gap-1.5 cursor-pointer shadow-md shadow-indigo-600/20"
                  >
                    <Download className="w-4 h-4" /> Download .md File
                  </button>
                </div>
              )}
            </div>

            {/* Modal Document Content Area */}
            <div className="flex-1 bg-[#0a0b10] p-6 sm:p-10 md:p-14 overflow-y-auto overflow-x-hidden">
              <div className="max-w-5xl mx-auto space-y-6 font-sans text-slate-300 overflow-x-hidden">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={blueprintMarkdownComponents}>
                  {cleanMarkdown(currentContent) || "_No content generated._"}
                </ReactMarkdown>
              </div>
            </div>

            {/* Modal Bottom Bar */}
            <div className="px-6 py-3 bg-slate-900/90 border-t border-slate-800/80 flex flex-wrap items-center justify-between text-xs font-mono text-slate-400 shrink-0 gap-2">
              <span>Disk Target: <span className="text-indigo-300 font-semibold">outputs/{activeProject.project_id}/{activeDocTab === "prd" ? "PRD.md" : "ARCHITECTURE.md"}</span></span>
              <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Pop-up Reader Active (1280px Wide Canvas)
              </span>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}



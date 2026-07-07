import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Zap, Activity, Users, Cpu, Shield, Terminal, Play, Send, Sparkles, FastForward, MessageSquare, AlertCircle, CheckCircle2 } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

const markdownComponents: any = {
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
            <Terminal className="w-3 h-3" /> Architecture Spec / Code
          </span>
          <span className="text-[9px] text-slate-500 uppercase tracking-wider">Markdown Snippet</span>
        </div>
        <pre className="p-3.5 overflow-x-auto text-[11px] font-mono leading-relaxed text-slate-200">
          <code {...props}>{children}</code>
        </pre>
      </div>
    );
  },
  table: ({ children }: any) => (
    <div className="overflow-x-auto my-3 rounded-xl border border-slate-800/80 shadow-md block">
      <table className="w-full text-left border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }: any) => <th className="bg-slate-900/90 p-2.5 font-bold text-slate-200 border-b border-slate-800/80 text-[11px] uppercase tracking-wider">{children}</th>,
  td: ({ children }: any) => <td className="p-2.5 border-b border-slate-800/50 text-slate-300 font-mono text-[11px]">{children}</td>,
  blockquote: ({ children }: any) => <blockquote className="border-l-4 border-indigo-500 pl-3.5 py-1.5 my-2.5 text-slate-300 italic bg-indigo-500/10 rounded-r-xl">{children}</blockquote>,
  ul: ({ children }: any) => <ul className="list-disc pl-5 my-2 space-y-1 text-slate-300">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal pl-5 my-2 space-y-1 text-slate-300">{children}</ol>,
  h1: ({ children }: any) => <h1 className="text-sm font-extrabold text-white my-3 border-b border-slate-800 pb-1.5 flex items-center gap-2">{children}</h1>,
  h2: ({ children }: any) => <h2 className="text-xs font-bold text-indigo-300 my-2.5 uppercase tracking-wider">{children}</h2>,
  h3: ({ children }: any) => <h3 className="text-xs font-semibold text-slate-200 my-2">{children}</h3>,
  p: ({ children }: any) => <div className="leading-relaxed my-1.5 text-slate-300">{children}</div>,
};

export function MADEngineArena() {
  const { 
    activeProject, 
    isStreaming, 
    liveStreams, 
    liveRound, 
    pendingInput, 
    resumeText, 
    setResumeText, 
    isResuming, 
    handleResume, 
    startSSEResumeStream 
  } = useMADEngine();
  
  const streamEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (streamEndRef.current) {
      streamEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [liveStreams, activeProject?.rounds_history]);

  return (
    <div className="bg-[#0d0e15]/90 border border-slate-800/80 rounded-2xl flex-1 min-h-0 flex flex-col shadow-2xl backdrop-blur-md overflow-hidden h-full">
      {/* Arena Header */}
      <div className="px-5 py-4 bg-slate-900/50 border-b border-slate-800/80 flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,1)]"></span>
          </span>
          <h2 className="text-xs font-black text-white uppercase tracking-wider flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-indigo-400" /> Live Debate Arena
          </h2>
        </div>
        {activeProject && (
          <span className="text-[10px] bg-indigo-500/10 text-indigo-300 font-bold px-2.5 py-1 rounded-lg border border-indigo-500/30 shadow-sm font-mono">
            ROUND {isStreaming && liveRound ? activeProject.rounds_history.length + 1 : activeProject.current_round}
          </span>
        )}
      </div>

      {/* Arena Message Thread */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {!activeProject ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 my-auto">
            <div className="p-4 bg-slate-900/60 rounded-2xl border border-slate-800/80 mb-3 shadow-inner">
              <Cpu className="w-10 h-10 text-slate-600 animate-pulse" />
            </div>
            <h3 className="text-sm font-bold text-slate-300 mb-1">MAD Engine Standby</h3>
            <p className="text-xs text-slate-500 max-w-[280px] leading-relaxed">
              Configure and launch a software blueprint project on the left panel to engage the AI debate system.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {/* Baseline Concept Banner */}
            <div className="p-4 bg-gradient-to-r from-indigo-950/40 via-indigo-900/20 to-transparent border border-indigo-500/30 rounded-xl shadow-md">
              <div className="flex items-center gap-2 mb-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">Baseline System Concept</span>
              </div>
              <p className="text-xs text-slate-200 leading-relaxed font-semibold italic">&quot;{activeProject.concept}&quot;</p>
            </div>

            {/* Render Grilling Chat History */}
            {activeProject.grill_history && activeProject.grill_history.length > 0 && (
              <div className="space-y-4 border-l-2 border-indigo-500/40 pl-4 ml-2 mb-6">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest my-2 flex items-center gap-2">
                  <Zap className="w-3 h-3 text-amber-400" /> Initial Architect Interview
                </div>
                {activeProject.grill_history.map((msg, mIdx) => (
                  <div key={mIdx} className={`p-4 rounded-xl border shadow-sm transition ${msg.role === "assistant" ? "bg-indigo-950/30 border-indigo-500/40" : "bg-slate-800/50 border-slate-700/60"}`}>
                    <div className="flex items-center gap-2 mb-2">
                      {msg.role === "assistant" ? (
                        <span className="text-[10px] font-bold text-indigo-300 uppercase flex items-center gap-1.5">
                          <Activity className="w-3.5 h-3.5 text-indigo-400" /> Performance Architect
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold text-slate-300 uppercase flex items-center gap-1.5">
                          <Users className="w-3.5 h-3.5 text-slate-400" /> Project Owner
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap font-mono prose prose-invert prose-xs max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Render Complete Debate Rounds from History */}
            {activeProject.rounds_history.map((round, rIdx) => (
              <div key={rIdx} className="space-y-4 border-l-2 border-indigo-500/30 pl-4 ml-2">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest my-2 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" /> Round {round.round_number} Transactions
                </div>
                
                {/* 1. Lead proposal draft */}
                <div className="bg-slate-900/70 border border-slate-800/90 border-l-4 border-l-emerald-500 rounded-xl p-4 shadow-md transition hover:border-slate-700">
                  <div className="flex justify-between items-center mb-2.5">
                    <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-emerald-400" /> Lead Architect (Performance & Scaling)
                    </span>
                    <span className="text-[9px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">NODE_2</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{round.proposal_draft}</ReactMarkdown>
                  </div>
                </div>

                {/* 2. Critics response */}
                {(() => {
                  const critiqueText = round.critique || "";
                  const hasSreSplit = critiqueText.includes("--- SRE CRITIQUE ---");
                  const parts = hasSreSplit ? critiqueText.split("--- SRE CRITIQUE ---") : [critiqueText];
                  const securityPart = parts[0];
                  const srePart = parts.length > 1 ? "--- SRE CRITIQUE ---\n" + parts[1] : null;

                  return (
                    <div className="flex flex-col gap-4">
                      <div className="bg-slate-900/70 border border-slate-800/90 border-l-4 border-l-rose-500 rounded-xl p-4 shadow-md transition hover:border-slate-700">
                        <div className="flex justify-between items-center mb-2.5">
                          <span className="text-xs font-bold text-rose-400 flex items-center gap-1.5">
                            <Shield className="w-3.5 h-3.5 text-rose-400" /> Security Auditor
                          </span>
                          <span className="text-[9px] bg-rose-500/10 text-rose-300 border border-rose-500/20 px-2 py-0.5 rounded font-mono">NODE_3A</span>
                        </div>
                        <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{securityPart}</ReactMarkdown>
                        </div>
                      </div>
                      
                      {srePart && (
                        <div className="bg-slate-900/70 border border-slate-800/90 border-l-4 border-l-cyan-500 rounded-xl p-4 shadow-md transition hover:border-slate-700">
                          <div className="flex justify-between items-center mb-2.5">
                            <span className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                              <Terminal className="w-3.5 h-3.5 text-cyan-400" /> SRE & Maintainability Lead
                            </span>
                            <span className="text-[9px] bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 px-2 py-0.5 rounded font-mono">NODE_3B</span>
                          </div>
                          <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{srePart}</ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* 3. Judge evaluation */}
                <div className="bg-gradient-to-r from-violet-950/30 via-slate-900/80 to-slate-900/80 border border-violet-500/30 rounded-xl p-4 shadow-lg">
                  <div className="flex justify-between items-center mb-2.5">
                    <span className="text-xs font-extrabold text-violet-300 flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5 text-violet-400" /> Independent Master Architect Judge
                    </span>
                    <span className="text-[9px] bg-violet-500/10 text-violet-300 border border-violet-500/20 px-2 py-0.5 rounded font-mono">NODE_4_EVAL</span>
                  </div>
                  <p className="text-[11px] text-slate-400 italic mb-3 leading-relaxed">&quot;Consolidated 6-pillar evaluation scores assigned for Turn {round.round_number}:&quot;</p>
                  
                  {/* Round Mini Scores */}
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {Object.entries(round.scores).map(([k, val]) => (
                      <div key={k} className="p-2 bg-slate-950/60 border border-slate-800/80 rounded-lg flex items-center justify-between text-[10px]">
                        <span className="text-slate-400 capitalize font-medium">{k.replace("_", " ")}</span>
                        <span className={`font-mono font-bold px-1.5 py-0.5 rounded ${val >= 0.85 ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : val >= 0.6 ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20" : "bg-rose-500/10 text-rose-400 border border-rose-500/20"}`}>
                          {val.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  {/* Display round's judge directive if any */}
                  {round.judge_directive && (
                    <div className="mt-3.5 p-3 bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded-xl text-xs flex items-start gap-2 shadow-sm">
                      <Zap className="w-4 h-4 text-amber-400 shrink-0 mt-0.5 animate-pulse" />
                      <div>
                        <span className="font-bold text-amber-200 block mb-0.5">Applied Judge Directive for Next Turn:</span>
                        <p className="font-mono text-[11px] text-amber-300/90 leading-relaxed">&quot;{round.judge_directive}&quot;</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Render Live Incremental Stream Output (If Speaking) */}
            {isStreaming && liveStreams.map((chunk, idx) => {
              let borderColor = "border-indigo-500";
              let textColor = "text-indigo-400";
              let bgColor = "bg-indigo-950/30";
              let pulseColor = "bg-indigo-400";
              let borderLeft = "border-l-indigo-500";
              
              if (chunk.agent?.includes("Performance")) {
                borderColor = "border-emerald-500";
                textColor = "text-emerald-400";
                bgColor = "bg-emerald-950/30";
                pulseColor = "bg-emerald-400";
                borderLeft = "border-l-emerald-500";
              } else if (chunk.agent?.includes("Security")) {
                borderColor = "border-rose-500";
                textColor = "text-rose-400";
                bgColor = "bg-rose-950/30";
                pulseColor = "bg-rose-400";
                borderLeft = "border-l-rose-500";
              } else if (chunk.agent?.includes("SRE")) {
                borderColor = "border-cyan-500";
                textColor = "text-cyan-400";
                bgColor = "bg-cyan-950/30";
                pulseColor = "bg-cyan-400";
                borderLeft = "border-l-cyan-500";
              } else if (chunk.agent?.includes("Judge") || chunk.agent?.includes("Synthesizing")) {
                borderColor = "border-violet-500";
                textColor = "text-violet-400";
                bgColor = "bg-violet-950/30";
                pulseColor = "bg-violet-400";
                borderLeft = "border-l-violet-500";
              }

              return (
                <div key={idx} className={`${bgColor} border ${borderColor}/40 rounded-xl p-4 animate-fade-in pl-4 border-l-4 ${borderLeft} shadow-lg backdrop-blur-sm`}>
                  <div className="flex justify-between items-center mb-2.5">
                    <span className={`text-xs font-bold ${textColor} flex items-center gap-2`}>
                      <Activity className="w-3.5 h-3.5 animate-spin" /> {chunk.agent || "Architect Agent..."}
                    </span>
                    <span className={`text-[9px] ${bgColor} ${textColor} px-2 py-0.5 rounded font-mono border ${borderColor}/30`}>STREAM_LIVE</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed font-mono prose prose-invert prose-xs max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{chunk.text}</ReactMarkdown>
                    {idx === liveStreams.length - 1 && (
                      <span className={`inline-block w-2 h-3.5 ${pulseColor} ml-1 animate-pulse rounded-sm align-middle`}></span>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={streamEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Panel: Dynamic RequestInput Handler with Override Guidance */}
      {activeProject && (
        <div className="p-4 bg-slate-900/80 border-t border-slate-800/80 flex flex-col gap-3 min-h-[110px] justify-center backdrop-blur-md">
          {pendingInput ? (
            <div className="flex flex-col gap-3 animate-fade-in">
              {/* Guidance Banner */}
              <div className="p-3 bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/40 rounded-xl flex items-start gap-3 shadow-md">
                <div className="p-1.5 bg-indigo-500/20 rounded-lg text-indigo-400 mt-0.5">
                  {pendingInput.name === "judge_review" ? <Sparkles className="w-4 h-4 animate-pulse" /> : <AlertCircle className="w-4 h-4 text-amber-400" />}
                </div>
                <div className="flex-1">
                  <span className="text-xs font-extrabold text-white uppercase tracking-wide flex items-center gap-1.5">
                    {pendingInput.name === "judge_review" ? "Architectural Override Mode (Judge Review)" : `Architect Interview: ${pendingInput.name}`}
                  </span>
                  <p className="text-[11px] text-slate-300 leading-relaxed mt-0.5">
                    {pendingInput.name === "judge_review" ? (
                      <>
                        The judge completed evaluation for Turn {activeProject.rounds_history.length}. Type custom architectural constraints below to steer Turn {activeProject.rounds_history.length + 1} (e.g. <span className="text-indigo-300 font-mono italic">&quot;Replace Redis with Memcached and reduce P99 target&quot;</span>), OR select a quick action:
                      </>
                    ) : (
                      <>{pendingInput.description}</>
                    )}
                  </p>
                </div>
              </div>

              {/* Custom Override Input Box */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  placeholder={
                    pendingInput.name === "judge_review"
                      ? "Type custom architectural directive or constraint..."
                      : "Type your answer to the architect's clarification..."
                  }
                  className="flex-1 text-xs bg-slate-950 border border-slate-700/80 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 rounded-xl px-3.5 py-2.5 text-slate-100 placeholder:text-slate-500 outline-none transition font-medium shadow-inner"
                  disabled={isResuming}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && resumeText.trim()) handleResume();
                  }}
                />
                <button
                  onClick={() => handleResume()}
                  disabled={isResuming || !resumeText.trim()}
                  className="px-4 py-2.5 bg-gradient-to-tr from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 rounded-xl font-bold text-xs transition flex items-center justify-center gap-1.5 min-w-[90px] shadow-md shadow-indigo-600/20 cursor-pointer"
                  title="Send Custom Directive"
                >
                  {isResuming ? <Activity className="w-4 h-4 animate-spin" /> : (
                    <>
                      <Send className="w-3.5 h-3.5" /> Send
                    </>
                  )}
                </button>
              </div>

              {/* Quick Action Buttons */}
              <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Quick Actions:</span>
                <div className="flex gap-2">
                  {pendingInput.name === "judge_review" && (
                    <>
                      <button 
                        onClick={() => handleResume("CONTINUE")} 
                        disabled={isResuming}
                        className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50 rounded-lg font-bold text-xs transition text-slate-200 flex items-center gap-1.5 cursor-pointer hover:border-slate-600 shadow-sm"
                        title="Proceed to next debate turn without custom override"
                      >
                        <FastForward className="w-3.5 h-3.5 text-indigo-400" /> Continue Debate
                      </button>
                      <button 
                        onClick={() => handleResume("SYNTHESIZE")} 
                        disabled={isResuming}
                        className="px-3.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 rounded-lg font-bold text-xs transition text-white flex items-center gap-1.5 shadow-[0_0_12px_rgba(16,185,129,0.3)] cursor-pointer"
                        title="End debate and compile final PRD.md & ARCHITECTURE.md"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" /> Force Synthesize Assets
                      </button>
                    </>
                  )}
                  
                  {pendingInput.name === "grill_question" && (
                    <button 
                      onClick={() => handleResume("SKIP_INTERVIEW")} 
                      disabled={isResuming}
                      className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 rounded-lg font-bold text-xs transition text-slate-300 border border-slate-700 flex items-center gap-1.5 cursor-pointer"
                    >
                      <FastForward className="w-3.5 h-3.5 text-amber-400" /> Skip Interview & Debate
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center text-center w-full h-full py-2">
              {isStreaming ? (
                <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-2 animate-pulse">
                  <Activity className="w-4 h-4 animate-spin text-indigo-500" /> Multi-Agent Graph Executing...
                </span>
              ) : (activeProject.consensus_achieved || Boolean(activeProject.final_prd) || Boolean(activeProject.final_architecture)) ? (
                <div className="flex items-center justify-center w-full px-2">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Debate Completed & Blueprints Synthesized
                  </span>
                </div>
              ) : (
                <div className="flex items-center justify-between w-full px-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-slate-500 animate-pulse"></span> Awaiting Next Round / Standby
                  </span>
                  <button
                    onClick={() => startSSEResumeStream(activeProject.project_id)}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-xl font-bold text-xs transition text-white shadow-[0_0_15px_rgba(79,70,229,0.4)] cursor-pointer"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    Resume Debate Session
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


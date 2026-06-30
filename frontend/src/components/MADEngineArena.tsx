import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Zap, Activity, Users, Cpu, Shield, Terminal, Play } from "lucide-react";
import { useMADEngine } from "../context/MADEngineContext";

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
    <div className="bg-[#0d0e15]/80 border border-slate-800/80 rounded-2xl flex-1 min-h-0 flex flex-col shadow-xl backdrop-blur-sm overflow-hidden h-full">
      {/* Arena Header */}
      <div className="px-5 py-4 bg-slate-900/40 border-b border-slate-800/60 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
          </span>
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">Live Debate Arena</h2>
        </div>
        {activeProject && (
          <span className="text-[10px] bg-slate-800 text-indigo-300 font-bold px-2 py-0.5 rounded border border-slate-700">
            ROUND {isStreaming && liveRound ? activeProject.rounds_history.length + 1 : activeProject.current_round}
          </span>
        )}
      </div>

      {/* Arena Message Thread */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 flex-1">
        {!activeProject ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6">
            <Cpu className="w-12 h-12 text-slate-700 mb-3 animate-pulse" />
            <h3 className="text-sm font-semibold text-slate-300 mb-1">MAD Engine Standby</h3>
            <p className="text-xs text-slate-500 max-w-[280px]">
              Configure and launch a software blueprint project on the left panel to engage the AI debate system.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Baseline Concept Banner */}
            <div className="p-4 bg-indigo-500/5 border border-indigo-500/20 rounded-xl">
              <div className="flex items-center gap-2 mb-1.5">
                <Zap className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400">Baseline System Concept</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-semibold">&quot;{activeProject.concept}&quot;</p>
            </div>

            {/* Render Grilling Chat History */}
            {activeProject.grill_history && activeProject.grill_history.length > 0 && (
              <div className="space-y-4 border-l-2 border-indigo-500/40 pl-4 ml-2 mb-6">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest my-2 flex items-center gap-2">
                  <Zap className="w-3 h-3" /> Initial Architect Interview
                </div>
                {activeProject.grill_history.map((msg, mIdx) => (
                  <div key={mIdx} className={`p-4 rounded-xl border ${msg.role === "assistant" ? "bg-indigo-950/20 border-indigo-500/30" : "bg-slate-800/40 border-slate-700/50"}`}>
                    <div className="flex items-center gap-2 mb-2">
                      {msg.role === "assistant" ? (
                        <span className="text-[10px] font-bold text-indigo-400 uppercase flex items-center gap-1.5">
                          <Activity className="w-3.5 h-3.5" /> Performance Architect
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold text-slate-400 uppercase flex items-center gap-1.5">
                          <Users className="w-3.5 h-3.5" /> Project Owner
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap font-mono">{msg.content}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Render Complete Debate Rounds from History */}
            {activeProject.rounds_history.map((round, rIdx) => (
              <div key={rIdx} className="space-y-4 border-l-2 border-indigo-500/20 pl-4 ml-2">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest my-2">Round {round.round_number} Transactions</div>
                
                {/* 1. Lead proposal draft */}
                <div className="bg-slate-900/60 border border-slate-800/80 border-l-4 border-l-emerald-500 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-2.5">
                    <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-emerald-400" /> Lead Architect (Performance & Scaling)
                    </span>
                    <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">NODE_2</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{round.proposal_draft}</ReactMarkdown>
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
                      <div className="bg-slate-900/60 border border-slate-800/80 border-l-4 border-l-rose-500 rounded-xl p-4">
                        <div className="flex justify-between items-center mb-2.5">
                          <span className="text-xs font-bold text-rose-400 flex items-center gap-1.5">
                            <Shield className="w-3.5 h-3.5 text-rose-400" /> Security Auditor
                          </span>
                          <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">NODE_3A</span>
                        </div>
                        <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{securityPart}</ReactMarkdown>
                        </div>
                      </div>
                      
                      {srePart && (
                        <div className="bg-slate-900/60 border border-slate-800/80 border-l-4 border-l-cyan-500 rounded-xl p-4">
                          <div className="flex justify-between items-center mb-2.5">
                            <span className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                            <Terminal className="w-3.5 h-3.5 text-cyan-400" /> SRE & Maintainability Lead
                          </span>
                            <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">NODE_3B</span>
                          </div>
                          <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{srePart}</ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* 3. Judge evaluation */}
                <div className="bg-[#121021] border border-violet-500/10 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-2.5">
                    <span className="text-xs font-bold text-violet-400 flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5 text-violet-400" /> Independent Master Architect Judge
                    </span>
                    <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">NODE_4_EVAL</span>
                  </div>
                  <p className="text-[11px] text-slate-400 italic mb-2 leading-relaxed">&quot;Consolidated scores assigned for Turn {round.round_number}.&quot;</p>
                  
                  {/* Round Mini Scores */}
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {Object.entries(round.scores).map(([k, val]) => (
                      <div key={k} className="p-2 bg-slate-900/40 border border-slate-800/50 rounded-lg flex items-center justify-between text-[10px]">
                        <span className="text-slate-400 capitalize">{k.replace("_", " ")}</span>
                        <span className={`font-mono font-bold ${val >= 0.85 ? "text-emerald-400" : val >= 0.6 ? "text-yellow-400" : "text-rose-400"}`}>
                          {val.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  {/* Display round's judge directive if any */}
                  {round.judge_directive && (
                    <div className="mt-3 p-2.5 bg-yellow-500/5 border border-yellow-500/20 text-yellow-400 rounded-lg text-[11px]">
                      <span className="font-bold">⚠️ Applied Directive:</span> &quot;{round.judge_directive}&quot;
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Render Live Incremental Stream Output (If Speaking) */}
            {isStreaming && liveStreams.map((chunk, idx) => {
              let borderColor = "border-indigo-500";
              let textColor = "text-indigo-400";
              let bgColor = "bg-indigo-950/20";
              let pulseColor = "bg-indigo-400";
              let borderLeft = "border-l-indigo-500";
              
              if (chunk.agent?.includes("Performance")) {
                borderColor = "border-emerald-500";
                textColor = "text-emerald-400";
                bgColor = "bg-emerald-950/20";
                pulseColor = "bg-emerald-400";
                borderLeft = "border-l-emerald-500";
              } else if (chunk.agent?.includes("Security")) {
                borderColor = "border-rose-500";
                textColor = "text-rose-400";
                bgColor = "bg-rose-950/20";
                pulseColor = "bg-rose-400";
                borderLeft = "border-l-rose-500";
              } else if (chunk.agent?.includes("SRE")) {
                borderColor = "border-cyan-500";
                textColor = "text-cyan-400";
                bgColor = "bg-cyan-950/20";
                pulseColor = "bg-cyan-400";
                borderLeft = "border-l-cyan-500";
              } else if (chunk.agent?.includes("Judge") || chunk.agent?.includes("Synthesizing")) {
                borderColor = "border-violet-500";
                textColor = "text-violet-400";
                bgColor = "bg-violet-950/20";
                pulseColor = "bg-violet-400";
                borderLeft = "border-l-violet-500";
              }

              return (
                <div key={idx} className={`${bgColor} border ${borderColor}/30 rounded-xl p-4 animate-fade-in pl-4 border-l-4 ${borderLeft}`}>
                  <div className="flex justify-between items-center mb-2.5">
                    <span className={`text-xs font-bold ${textColor} flex items-center gap-1.5`}>
                      <Activity className="w-3.5 h-3.5 animate-spin" /> {chunk.agent || "Architect Agent..."}
                    </span>
                    <span className={`text-[9px] ${bgColor} ${textColor} px-2 py-0.5 rounded font-mono`}>STREAM_LIVE</span>
                  </div>
                  <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed font-mono prose prose-invert prose-xs max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{chunk.text}</ReactMarkdown>
                    {idx === liveStreams.length - 1 && (
                      <span className={`inline-block w-1.5 h-3 ${pulseColor} ml-0.5 animate-pulse`}></span>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={streamEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Panel: Dynamic RequestInput Handler */}
      {activeProject && (
        <div className="p-4 bg-slate-900/40 border-t border-slate-800/60 flex flex-col gap-3 min-h-[100px] justify-center">
          {pendingInput ? (
            <div className="flex flex-col gap-2 animate-fade-in">
              <span className="text-[10px] font-bold text-yellow-400 uppercase tracking-wider flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5" /> Action Required: {pendingInput.name}
              </span>
              <p className="text-[11px] text-slate-400 leading-relaxed">{pendingInput.description}</p>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  placeholder="Type your response or directive..."
                  className="flex-1 text-xs bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 rounded-xl px-3 py-2 text-slate-100 placeholder:text-slate-600 outline-none transition"
                  disabled={isResuming}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && resumeText.trim()) handleResume();
                  }}
                />
                <button
                  onClick={() => handleResume()}
                  disabled={isResuming || !resumeText.trim()}
                  className="px-4 py-2 bg-gradient-to-tr from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 rounded-xl font-bold text-xs transition flex items-center justify-center min-w-[70px]"
                >
                  {isResuming ? <Activity className="w-4 h-4 animate-spin" /> : "Send"}
                </button>
                
                {pendingInput.name === "judge_review" && (
                  <>
                    <button 
                      onClick={() => handleResume("CONTINUE")} 
                      disabled={isResuming}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 rounded-xl font-bold text-xs transition text-white"
                    >
                      Continue Debate
                    </button>
                    <button 
                      onClick={() => handleResume("SYNTHESIZE")} 
                      disabled={isResuming}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-xl font-bold text-xs transition text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                    >
                      Synthesize Assets
                    </button>
                  </>
                )}
                
                {pendingInput.name === "grill_question" && (
                  <button 
                    onClick={() => handleResume("SKIP_INTERVIEW")} 
                    disabled={isResuming}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 rounded-xl font-bold text-xs transition text-white border border-slate-600"
                  >
                    Skip Interview
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center text-center w-full h-full">
              {isStreaming ? (
                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-2 animate-pulse">
                  <Activity className="w-3.5 h-3.5" /> Graph Executing...
                </span>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                    Awaiting Next Round
                  </span>
                  {!activeProject.consensus_achieved && (
                    <button
                      onClick={() => startSSEResumeStream(activeProject.project_id)}
                      className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-xs transition text-white shadow-[0_0_15px_rgba(79,70,229,0.4)]"
                    >
                      <Play className="w-4 h-4" />
                      Resume Debate Session
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

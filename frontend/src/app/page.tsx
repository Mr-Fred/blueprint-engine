"use client";
import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  Play, 
  Send, 
  Zap, 
  Shield, 
  Terminal, 
  CheckCircle, 
  AlertCircle, 
  Cpu, 
  Activity, 
  FileText, 
  Code, 
  Layers, 
  DollarSign, 
  Users, 
  ArrowRight,
  Sparkles,
  Clipboard,
  Check,
  Trash2
} from "lucide-react";
import { Group, Panel, Separator } from "react-resizable-panels";
// API Base URL
const API_BASE = "http://localhost:8000";
// Define the core types corresponding to the backend Pydantic models
interface PillarScores {
  performance: number;
  scalability: number;
  security: number;
  reliability: number;
  maintainability: number;
  cost_efficiency: number;
}
interface DebateRound {
  round_number: number;
  proposal_draft: string;
  critique: string;
  scores: PillarScores;
  judge_directive: string | null;
}
interface DebateState {
  project_id: string;
  concept: string;
  current_round: number;
  rounds_history: DebateRound[];
  grill_history?: {role: string, content: string}[];
  consensus_achieved: boolean;
  final_prd: string | null;
  final_architecture: string | null;
}
interface ProjectInfo {
  project_id: string;
  concept: string;
  status: string;
}
interface LiveStreamChunk {
  agent: string | null;
  text: string;
}
export default function Home() {
  // Application States
  const [conceptInput, setConceptInput] = useState("");
  const [activeProject, setActiveProject] = useState<DebateState | null>(null);
  const [projectsList, setProjectsList] = useState<ProjectInfo[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  
  // Real-time incremental streams
  const [liveAgent, setLiveAgent] = useState<string | null>(null);
  const [liveStreams, setLiveStreams] = useState<LiveStreamChunk[]>([]);
  const [liveRound, setLiveRound] = useState<number>(1);
  
  // RequestInput Resumability
  const [pendingInput, setPendingInput] = useState<{name: string, description: string} | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [isResuming, setIsResuming] = useState(false);
  
  // Tab View for final documents
  const [activeDocTab, setActiveDocTab] = useState<"prd" | "architecture">("prd");
  const [copied, setCopied] = useState(false);
  const streamEndRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<EventSource | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setIsMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);
  // Suggested concepts for quick starting
  const SUGGESTED_CONCEPTS = [
    "High-throughput collaborative design whiteboard with canvas synchronization",
    "Jailed serverless microservices runtime executing untrusted sandboxed code",
    "Real-time fraud prevention engine with sub-10ms transactional latency limits"
  ];
  // Auto-scroll the live debate feed
  useEffect(() => {
    if (streamEndRef.current) {
      streamEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [liveStreams, activeProject?.rounds_history]);
  // Load existing projects on mount
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/projects`);
        if (res.ok) {
          const data: ProjectInfo[] = await res.json();
          setProjectsList(data);
        }
      } catch (err) {
        console.error("Error fetching projects list:", err);
      }
    };
    fetchProjects();
  }, []);
  // Load project state from the backend
  const fetchProjectState = async (projectId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/state`);
      if (res.ok) {
        const data: DebateState = await res.json();
        setActiveProject(data);
      }
    } catch (err) {
      console.error("Error fetching project state:", err);
    }
  };
  // Start a new debate
  const handleStartDebate = async (conceptText: string) => {
    if (!conceptText.trim()) return;
    setStreamError(null);
    setLiveStreams([]);
    setLiveAgent(null);
    
    try {
      // 1. Initialize project
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concept: conceptText }),
      });
      
      if (!res.ok) throw new Error("Failed to initialize project on backend.");
      const projInfo = await res.json();
      
      const newProj: ProjectInfo = {
        project_id: projInfo.project_id,
        concept: conceptText,
        status: "active"
      };
      
      setProjectsList(prev => [newProj, ...prev]);
      
      // Initialize a local placeholder state
      const initialStoreState: DebateState = {
        project_id: projInfo.project_id,
        concept: conceptText,
        current_round: 1,
        rounds_history: [],
        grill_history: [],
        consensus_achieved: false,
        final_prd: null,
        final_architecture: null
      };
      setActiveProject(initialStoreState);
      
      // 2. Open SSE stream
      startSSEStream(projInfo.project_id);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Something went wrong.";
      setStreamError(errMsg);
    }
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const processSSEEvent = (rawData: any, projectId: string, closeStream: () => void) => {
    // Detect ADK 2.0 RequestInput suspension
      if (rawData.request_input) {
        setPendingInput({
          name: rawData.request_input.name,
          description: rawData.request_input.description
        });
        // The graph is paused. Wait for SUSPENDED event to close stream and sync state.
        return;
      }
      
      if (rawData.event_type === "SUSPENDED") {
        setActiveProject(rawData.state);
        setIsStreaming(false);
        setLiveAgent(null);
        setLiveStreams([]);
        closeStream();
        return;
      }
    if (rawData.event_type === "COMPLETE") {
      setIsStreaming(false);
      setActiveProject(rawData.state);
      setLiveAgent(null);
      setLiveStreams([]);
      closeStream();
      return;
    }
    
    if (rawData.event_type === "ERROR") {
      setIsStreaming(false);
      setStreamError(rawData.message);
      closeStream();
      return;
    }
    
    const content = rawData.content;
    const output = rawData.output;
    
    let currentAgentName = null;
    if (rawData.node_path) {
      const path = rawData.node_path.toLowerCase();
      if (path.includes("performance_agent_node") || path.includes("grill_node")) {
        currentAgentName = "Performance & Scaling Architect";
      } else if (path.includes("security_agent_node")) {
        currentAgentName = "Security & Resilience Auditor";
      } else if (path.includes("devops_agent_node")) {
        currentAgentName = "DevOps & Maintainability Lead";
      } else if (path.includes("evaluate_and_score_node")) {
        currentAgentName = "Master Architect Judge";
      } else if (path.includes("synthesis_node")) {
        currentAgentName = "Synthesizing Final Assets...";
      }
      if (currentAgentName) setLiveAgent(currentAgentName);
    }
    if (content && content.parts) {
      const textChunk = content.parts.map((p: { text?: string }) => p.text || "").join("");
      if (textChunk) {
        setLiveStreams(prev => {
          const lastChunk = prev.length > 0 ? prev[prev.length - 1] : null;
          const agentToUse = currentAgentName || (lastChunk ? lastChunk.agent : null);
          
          if (lastChunk && lastChunk.agent === agentToUse) {
            const updated = [...prev];
            updated[updated.length - 1] = { ...lastChunk, text: lastChunk.text + textChunk };
            return updated;
          } else {
            return [...prev, { agent: agentToUse, text: textChunk }];
          }
        });
      }
    }
    
    if (output) {
      fetchProjectState(projectId);
    }
  };
  // Establish SSE Event Source Connection
  const startSSEStream = (projectId: string) => {
    if (sseRef.current) {
      sseRef.current.close();
    }
    
    setIsStreaming(true);
    setPendingInput(null);
    const eventSource = new EventSource(`${API_BASE}/api/projects/${projectId}/stream`);
    sseRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      try {
        const rawData = JSON.parse(event.data);
        processSSEEvent(rawData, projectId, () => eventSource.close());
      } catch (err) {
        console.error("Error parsing SSE frame:", err);
      }
    };
    
    eventSource.onerror = (err) => {
      console.error("SSE Connection error, closing:", err);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  const startSSEResumeStream = (projectId: string) => {
    if (sseRef.current) {
      sseRef.current.close();
    }
    
    setIsStreaming(true);
    setPendingInput(null);
    const eventSource = new EventSource(`${API_BASE}/api/projects/${projectId}/resume_stream`);
    sseRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      try {
        const rawData = JSON.parse(event.data);
        processSSEEvent(rawData, projectId, () => eventSource.close());
      } catch (err) {
        console.error("Error parsing SSE frame:", err);
      }
    };
    
    eventSource.onerror = (err) => {
      console.error("SSE Connection error, closing:", err);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  // Custom fetch-based streaming reader for the POST /resume endpoint
  const handleResume = async (overrideAction?: string) => {
    if (!activeProject || !pendingInput) return;
    setIsResuming(true);
    
    const payloadText = overrideAction !== undefined ? overrideAction : resumeText;
    
    try {
      const res = await fetch(`${API_BASE}/api/projects/${activeProject.project_id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          input_name: pendingInput.name,
          user_response: payloadText 
        }),
      });
      
      if (!res.ok) throw new Error("Resume failed");
      
      setPendingInput(null);
      setResumeText("");
      setIsResuming(false);
      setIsStreaming(true);
      
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      
      if (reader) {
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            setIsStreaming(false);
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";
          
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const dataStr = line.replace("data: ", "");
                const rawData = JSON.parse(dataStr);
                processSSEEvent(rawData, activeProject.project_id, () => {
                   reader.cancel();
                });
              } catch (e) {
                 // ignore partial parse error
              }
            }
          }
        }
      }
    } catch (err) {
      console.error("Failed to resume debate:", err);
      setIsResuming(false);
    }
  };

  const handleDeleteProject = async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setProjectsList(prev => prev.filter(p => p.project_id !== projectId));
        if (activeProject?.project_id === projectId) {
          setActiveProject(null);
        }
      } else {
        console.error("Failed to delete project");
      }
    } catch (err) {
      console.error("Error deleting project:", err);
    }
  };
  // Copy document markdown to clipboard
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  // Helper to format scores
  const getScoreColor = (score: number) => {
    if (score >= 0.85) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    if (score >= 0.6) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/30";
    return "text-rose-400 bg-rose-500/10 border-rose-500/30";
  };
  const getScoreBgBar = (score: number) => {
    if (score >= 0.85) return "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]";
    if (score >= 0.6) return "bg-yellow-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]";
    return "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]";
  };

  // Clean-up connection on unmount
  useEffect(() => {
    return () => {
      if (sseRef.current) sseRef.current.close();
    };
  }, []);
  if (!isMounted) {
    return (
      <main className="min-h-screen bg-[#090a10] text-slate-100 flex items-center justify-center font-sans">
        <div className="flex flex-col items-center gap-3">
          <Cpu className="w-10 h-10 text-indigo-500 animate-spin" />
          <p className="text-xs text-slate-400">Loading MAD Engine...</p>
        </div>
      </main>
    );
  }
  return (
    <main className="h-screen overflow-hidden bg-[#090a10] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(99,102,241,0.12),rgba(255,255,255,0))] text-slate-100 flex flex-col font-sans">
      
      {/* Top Premium Navbar */}
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
        {/* Streaming Status Indicator */}
        <div className="flex items-center gap-4">
          {activeProject && (
            <div className="text-xs font-mono text-slate-400 bg-slate-800/40 border border-slate-700/50 px-3 py-1.5 rounded-lg flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,1)]"></span>
              ID: <span className="text-indigo-300 font-semibold">{activeProject.project_id}</span>
            </div>
          )}
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
      {/* Main Grid Layout */}
      <div className="flex-1 min-h-0 overflow-hidden p-6 max-w-[1800px] w-full mx-auto h-[calc(100vh-85px)]">
        <Group orientation="horizontal" className="h-full">
        
        {/* Left column - Setup & Project List (3 Cols) */}
        <Panel defaultSize="25%" minSize="15%" maxSize="40%" className="flex flex-col gap-6 pr-3 min-h-0">
          
          {/* Section 1: Concept Launchpad */}
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
            {streamError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl flex items-start gap-2 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{streamError}</span>
              </div>
            )}
            {/* Quick-start Suggestions */}
            <div className="mt-2">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block mb-2">Suggestions</span>
              <div className="flex flex-col gap-1.5">
                {SUGGESTED_CONCEPTS.map((concept, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setConceptInput(concept);
                    }}
                    disabled={isStreaming}
                    className="text-left text-[11px] text-slate-400 bg-slate-900/30 hover:bg-slate-800/40 border border-slate-800/60 p-2 rounded-lg leading-snug transition"
                  >
                    {concept}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {/* Section 2: Active Projects History */}
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
        </Panel>
        <Separator className="w-1.5 rounded-full bg-slate-800/50 hover:bg-indigo-500/50 transition-colors mx-1 cursor-col-resize" />
        {/* Center column - The Debate Arena Monitor (5 Cols) */}
        <Panel defaultSize="45%" minSize="30%" className="flex flex-col gap-6 px-3 min-h-0">
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
                      <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
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
                        const hasDevopsSplit = critiqueText.includes("--- DEVOPS CRITIQUE ---");
                        const parts = hasDevopsSplit ? critiqueText.split("--- DEVOPS CRITIQUE ---") : [critiqueText];
                        const securityPart = parts[0];
                        const devopsPart = parts.length > 1 ? "--- DEVOPS CRITIQUE ---\n" + parts[1] : null;
                        return (
                          <div className="flex flex-col gap-4">
                            <div className="bg-slate-900/60 border border-slate-800/80 border-l-4 border-l-rose-500 rounded-xl p-4">
                              <div className="flex justify-between items-center mb-2.5">
                                <span className="text-xs font-bold text-rose-400 flex items-center gap-1.5">
                                  <Shield className="w-3.5 h-3.5 text-rose-400" /> Security & Resilience Auditor
                                </span>
                                <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">NODE_3A</span>
                              </div>
                              <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{securityPart}</ReactMarkdown>
                              </div>
                            </div>
                            {devopsPart && (
                              <div className="bg-slate-900/60 border border-slate-800/80 border-l-4 border-l-cyan-500 rounded-xl p-4">
                                <div className="flex justify-between items-center mb-2.5">
                                  <span className="text-xs font-bold text-cyan-400 flex items-center gap-1.5">
                                    <Layers className="w-3.5 h-3.5 text-cyan-400" /> DevOps & Maintainability Lead
                                  </span>
                                  <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">NODE_3B</span>
                                </div>
                                <div className="text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed prose prose-invert prose-xs max-w-none">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{devopsPart}</ReactMarkdown>
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
                    } else if (chunk.agent?.includes("DevOps")) {
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
        </Panel>
        <Separator className="w-1.5 rounded-full bg-slate-800/50 hover:bg-indigo-500/50 transition-colors mx-1 cursor-col-resize" />
        {/* Right column - Consensus, Scores, and Document Synthesizer (4 Cols) */}
        <Panel defaultSize="30%" minSize="20%" maxSize="50%" className="flex flex-col gap-6 pl-3 min-h-0">
          
          {/* 6-Pillar Metric Gauge */}
          <div className="bg-[#0d0e15]/80 border border-slate-800/80 rounded-2xl p-5 flex flex-col gap-5 shadow-xl backdrop-blur-sm">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-indigo-400" /> Consensus Dashboard
            </h2>
            {!activeProject || activeProject.rounds_history.length === 0 ? (
              <div className="text-center p-6 bg-slate-900/30 border border-slate-800/50 rounded-xl flex flex-col items-center justify-center">
                <AlertCircle className="w-8 h-8 text-slate-600 mb-2" />
                <p className="text-[11px] text-slate-500">Wait for Round 1 evaluation to compute quality metrics</p>
              </div>
            ) : (
              <div className="space-y-4">
                
                {/* Visual Circle Meter */}
                <div className="flex items-center justify-center p-2">
                  <div className="relative flex items-center justify-center">
                    <svg className="w-24 h-24 transform -rotate-90">
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        className="stroke-slate-800"
                        strokeWidth="6"
                        fill="transparent"
                      />
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        className={activeProject.consensus_achieved ? "stroke-emerald-500" : "stroke-indigo-500"}
                        strokeWidth="6"
                        fill="transparent"
                        strokeDasharray={251.2}
                        strokeDashoffset={251.2 - (251.2 * (activeProject.consensus_achieved ? 1.0 : 0.70))}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute flex flex-col items-center justify-center text-center">
                      <span className="text-[10px] text-slate-500 uppercase font-bold tracking-tight">Status</span>
                      <span className="text-xs font-bold text-white uppercase tracking-tight">
                        {activeProject.consensus_achieved ? "Verified" : "Debating"}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Pillar Metrics (Threshold ≥ 0.85)</span>
                  
                  {/* Render 6 Pillar Bars from Latest Round */}
                  {Object.entries(activeProject.rounds_history[activeProject.rounds_history.length - 1].scores).map(([pillar, val]) => (
                    <div key={pillar} className="space-y-1">
                      <div className="flex justify-between items-center text-xs">
                        <span className="capitalize text-slate-300 flex items-center gap-1.5">
                          {pillar === "performance" && <Cpu className="w-3 h-3 text-emerald-400" />}
                          {pillar === "scalability" && <Layers className="w-3 h-3 text-cyan-400" />}
                          {pillar === "security" && <Shield className="w-3 h-3 text-rose-400" />}
                          {pillar === "reliability" && <Zap className="w-3 h-3 text-yellow-400" />}
                          {pillar === "maintainability" && <Code className="w-3 h-3 text-violet-400" />}
                          {pillar === "cost_efficiency" && <DollarSign className="w-3 h-3 text-amber-400" />}
                          {pillar.replace("_", " ")}
                        </span>
                        <span className={`font-mono font-bold px-2 py-0.5 rounded border text-[10px] ${getScoreColor(val)}`}>
                          {val.toFixed(2)}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${getScoreBgBar(val)}`}
                          style={{ width: `${val * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          {/* synthesized Document compilation panel */}
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
        </Panel>
        </Group>
      </div>
    </main>
  );
}

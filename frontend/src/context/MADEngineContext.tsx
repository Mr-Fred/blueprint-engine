"use client";
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import { DebateState, ProjectInfo, LiveStreamChunk, PendingInput } from "../types/mad-engine";
import { useDebateStream } from "../hooks/useDebateStream";

const API_BASE = "http://localhost:8000";

interface MADEngineContextValue {
  conceptInput: string;
  setConceptInput: React.Dispatch<React.SetStateAction<string>>;
  activeProject: DebateState | null;
  setActiveProject: React.Dispatch<React.SetStateAction<DebateState | null>>;
  projectsList: ProjectInfo[];
  setProjectsList: React.Dispatch<React.SetStateAction<ProjectInfo[]>>;
  isMounted: boolean;
  
  // From useDebateStream
  isStreaming: boolean;
  streamError: string | null;
  liveAgent: string | null;
  liveStreams: LiveStreamChunk[];
  liveRound: number;
  pendingInput: PendingInput | null;
  resumeText: string;
  setResumeText: React.Dispatch<React.SetStateAction<string>>;
  isResuming: boolean;
  
  // Actions
  handleStartDebate: (conceptText: string) => Promise<void>;
  handleResume: (overrideAction?: string) => Promise<void>;
  handleDeleteProject: (projectId: string, e: React.MouseEvent) => Promise<void>;
  fetchProjectState: (projectId: string) => Promise<void>;
  startSSEResumeStream: (projectId: string) => void;
}

const MADEngineContext = createContext<MADEngineContextValue | undefined>(undefined);

export function MADEngineProvider({ children }: { children: React.ReactNode }) {
  const [conceptInput, setConceptInput] = useState("");
  const [activeProject, setActiveProject] = useState<DebateState | null>(null);
  const [projectsList, setProjectsList] = useState<ProjectInfo[]>([]);
  const [isMounted, setIsMounted] = useState(false);
  const [liveRound, setLiveRound] = useState<number>(1);

  useEffect(() => {
    const timer = setTimeout(() => setIsMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  const fetchProjectState = useCallback(async (projectId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/state`);
      if (res.ok) {
        const data: DebateState = await res.json();
        setActiveProject(data);
      }
    } catch (err) {
      console.error("Error fetching project state:", err);
    }
  }, []);

  const {
    isStreaming,
    streamError,
    liveAgent,
    liveStreams,
    pendingInput,
    resumeText,
    setResumeText,
    isResuming,
    startSSEStream,
    startSSEResumeStream,
    handleResume: streamHandleResume,
    setStreamError,
    setLiveStreams,
    setLiveAgent
  } = useDebateStream({
    onStateUpdate: setActiveProject,
    onFetchState: fetchProjectState
  });

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

  const handleStartDebate = useCallback(async (conceptText: string) => {
    if (!conceptText.trim()) return;
    setStreamError(null);
    setLiveStreams([]);
    setLiveAgent(null);
    
    try {
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
      
      startSSEStream(projInfo.project_id);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Something went wrong.";
      setStreamError(errMsg);
    }
  }, [setStreamError, setLiveStreams, setLiveAgent, startSSEStream]);

  const handleDeleteProject = useCallback(async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setProjectsList(prev => prev.filter(p => p.project_id !== projectId));
        setActiveProject(prev => prev?.project_id === projectId ? null : prev);
      } else {
        console.error("Failed to delete project");
      }
    } catch (err) {
      console.error("Error deleting project:", err);
    }
  }, []);

  const handleResumeContext = useCallback(async (overrideAction?: string) => {
    if (activeProject) {
      await streamHandleResume(activeProject.project_id, overrideAction);
    }
  }, [activeProject, streamHandleResume]);

  const contextValue = useMemo(() => ({
    conceptInput,
    setConceptInput,
    activeProject,
    setActiveProject,
    projectsList,
    setProjectsList,
    isMounted,
    liveRound,
    isStreaming,
    streamError,
    liveAgent,
    liveStreams,
    pendingInput,
    resumeText,
    setResumeText,
    isResuming,
    handleStartDebate,
    handleResume: handleResumeContext,
    handleDeleteProject,
    fetchProjectState,
    startSSEResumeStream
  }), [
    conceptInput, activeProject, projectsList, isMounted, liveRound, 
    isStreaming, streamError, liveAgent, liveStreams, pendingInput, 
    resumeText, isResuming, handleStartDebate, handleResumeContext, 
    handleDeleteProject, fetchProjectState, startSSEResumeStream
  ]);

  return (
    <MADEngineContext.Provider value={contextValue}>
      {children}
    </MADEngineContext.Provider>
  );
}

export function useMADEngine() {
  const context = useContext(MADEngineContext);
  if (context === undefined) {
    throw new Error("useMADEngine must be used within a MADEngineProvider");
  }
  return context;
}

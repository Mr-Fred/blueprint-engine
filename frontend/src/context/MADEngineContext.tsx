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
  cavemanMode: boolean;
  setCavemanMode: React.Dispatch<React.SetStateAction<boolean>>;
  
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
  toggleCavemanMode: (newMode?: boolean) => Promise<void>;
  sendIntermissionAction: (action: string, note?: string) => Promise<void>;
}

const MADEngineContext = createContext<MADEngineContextValue | undefined>(undefined);

export function MADEngineProvider({ children }: { children: React.ReactNode }) {
  const [conceptInput, setConceptInput] = useState("");
  const [activeProject, setActiveProject] = useState<DebateState | null>(null);
  const [projectsList, setProjectsList] = useState<ProjectInfo[]>([]);
  const [isMounted, setIsMounted] = useState(false);
  const [liveRound, setLiveRound] = useState<number>(1);
  const [cavemanMode, setCavemanMode] = useState<boolean>(true);

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
        if (data.caveman_mode !== undefined) {
          setCavemanMode(data.caveman_mode);
        }
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
    onStateUpdate: (state) => {
      setActiveProject(state);
      if (state?.caveman_mode !== undefined) {
        setCavemanMode(state.caveman_mode);
      }
    },
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

  const toggleCavemanMode = useCallback(async (newMode?: boolean) => {
    const targetMode = newMode !== undefined ? newMode : !cavemanMode;
    setCavemanMode(targetMode);
    if (activeProject) {
      try {
        const res = await fetch(`${API_BASE}/api/projects/${activeProject.project_id}/toggle-caveman`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ caveman_mode: targetMode }),
        });
        if (res.ok) {
          const updatedState: DebateState = await res.json();
          setActiveProject(updatedState);
        }
      } catch (err) {
        console.error("Failed to toggle caveman mode:", err);
      }
    }
  }, [cavemanMode, activeProject]);

  const handleStartDebate = useCallback(async (conceptText: string) => {
    if (!conceptText.trim()) return;
    setStreamError(null);
    setLiveStreams([]);
    setLiveAgent(null);
    
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concept: conceptText, caveman_mode: cavemanMode }),
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
        final_architecture: null,
        caveman_mode: cavemanMode
      };
      setActiveProject(initialStoreState);
      
      startSSEStream(projInfo.project_id);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Something went wrong.";
      setStreamError(errMsg);
    }
  }, [cavemanMode, setStreamError, setLiveStreams, setLiveAgent, startSSEStream]);

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

  const sendIntermissionAction = useCallback(async (action: string, note?: string) => {
    if (!activeProject) return;
    try {
      await fetch(`${API_BASE}/api/projects/${activeProject.project_id}/intermission`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, steering_note: note }),
      });
      await handleResumeContext(action);
    } catch (e) {
      console.error("Failed to send intermission action:", e);
    }
  }, [activeProject, handleResumeContext]);

  const contextValue = useMemo(() => ({
    conceptInput,
    setConceptInput,
    activeProject,
    setActiveProject,
    projectsList,
    setProjectsList,
    isMounted,
    cavemanMode,
    setCavemanMode,
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
    startSSEResumeStream,
    toggleCavemanMode,
    sendIntermissionAction
  }), [
    conceptInput, activeProject, projectsList, isMounted, cavemanMode, liveRound, 
    isStreaming, streamError, liveAgent, liveStreams, pendingInput, 
    resumeText, isResuming, handleStartDebate, handleResumeContext, 
    handleDeleteProject, fetchProjectState, startSSEResumeStream, toggleCavemanMode,
    sendIntermissionAction
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

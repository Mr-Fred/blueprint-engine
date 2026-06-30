import { useState, useRef, useEffect, useCallback } from "react";
import { LiveStreamChunk, PendingInput, DebateState } from "../types/mad-engine";

const API_BASE = "http://localhost:8000";

interface UseDebateStreamOptions {
  onStateUpdate: (state: DebateState) => void;
  onFetchState: (projectId: string) => void;
}

export function useDebateStream({ onStateUpdate, onFetchState }: UseDebateStreamOptions) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [liveAgent, setLiveAgent] = useState<string | null>(null);
  const [liveStreams, setLiveStreams] = useState<LiveStreamChunk[]>([]);
  const [pendingInput, setPendingInput] = useState<PendingInput | null>(null);
  
  const [resumeText, setResumeText] = useState("");
  const [isResuming, setIsResuming] = useState(false);

  const sseRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      if (sseRef.current) sseRef.current.close();
    };
  }, []);

  const processSSEEvent = useCallback((rawData: any, projectId: string, closeStream: () => void) => {
    // Detect ADK 2.0 RequestInput suspension
    if (rawData.request_input) {
      setPendingInput({
        name: rawData.request_input.name,
        description: rawData.request_input.description
      });
      return;
    }
    
    if (rawData.event_type === "SUSPENDED") {
      onStateUpdate(rawData.state);
      setIsStreaming(false);
      setLiveAgent(null);
      setLiveStreams([]);
      closeStream();
      return;
    }

    if (rawData.event_type === "COMPLETE") {
      setIsStreaming(false);
      onStateUpdate(rawData.state);
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
    const rawPath = rawData.node_path || (rawData.nodeInfo && rawData.nodeInfo.path) || (rawData.node_info && rawData.node_info.path);
    if (rawPath) {
      const path = String(rawPath).toLowerCase();
      if (path.includes("performance_agent_node") || path.includes("grill_node")) {
        currentAgentName = "Performance & Scaling Architect";
      } else if (path.includes("security_agent_node")) {
        currentAgentName = "Security & Resilience Auditor";
      } else if (path.includes("sre_agent_node")) {
        currentAgentName = "SRE & Maintainability Lead";
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
          
          const existingIndex = prev.findIndex(chunk => chunk.agent === agentToUse);
          
          if (existingIndex !== -1) {
            const updated = [...prev];
            updated[existingIndex] = { ...updated[existingIndex], text: updated[existingIndex].text + textChunk };
            return updated;
          } else {
            return [...prev, { agent: agentToUse, text: textChunk }];
          }
        });
      }
    }
    
    if (output) {
      onFetchState(projectId);
    }
  }, [onStateUpdate, onFetchState]);

  const startSSEStream = useCallback((projectId: string) => {
    if (sseRef.current) sseRef.current.close();
    
    setIsStreaming(true);
    setStreamError(null);
    setPendingInput(null);
    setLiveStreams([]);
    setLiveAgent(null);

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
  }, [processSSEEvent]);

  const startSSEResumeStream = useCallback((projectId: string) => {
    if (sseRef.current) sseRef.current.close();
    
    setIsStreaming(true);
    setStreamError(null);
    setPendingInput(null);
    setLiveStreams([]);
    setLiveAgent(null);

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
  }, [processSSEEvent]);

  const handleResume = useCallback(async (projectId: string, overrideAction?: string) => {
    if (!pendingInput) return;
    setIsResuming(true);
    
    const payloadText = overrideAction !== undefined ? overrideAction : resumeText;
    
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/resume`, {
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
                processSSEEvent(rawData, projectId, () => {
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
  }, [pendingInput, resumeText, processSSEEvent]);

  return {
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
    handleResume,
    setStreamError,
    setLiveStreams,
    setLiveAgent
  };
}

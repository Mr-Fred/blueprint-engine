"use client";
import React from "react";
import { Cpu } from "lucide-react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { MADEngineProvider, useMADEngine } from "../context/MADEngineContext";
import { MADEngineHeader } from "../components/MADEngineHeader";
import { MADEngineLauncher } from "../components/MADEngineLauncher";
import { MADEngineRegistry } from "../components/MADEngineRegistry";
import { MADEngineArena } from "../components/MADEngineArena";
import { MADEngineConsensus } from "../components/MADEngineConsensus";
import { MADEngineBlueprints } from "../components/MADEngineBlueprints";

function MADEngineLayout() {
  const { isMounted } = useMADEngine();

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
      <MADEngineHeader />
      
      {/* Main Grid Layout */}
      <div className="flex-1 min-h-0 overflow-hidden p-6 max-w-[1800px] w-full mx-auto h-[calc(100vh-85px)]">
        <Group orientation="horizontal" className="h-full">
          
          {/* Left column - Setup & Project List */}
          <Panel defaultSize="25%" minSize="15%" maxSize="40%" className="flex flex-col gap-6 pr-3 min-h-0">
            <MADEngineLauncher />
            <MADEngineRegistry />
          </Panel>
          
          <Separator className="w-1.5 rounded-full bg-slate-800/50 hover:bg-indigo-500/50 transition-colors mx-1 cursor-col-resize" />
          
          {/* Center column - The Debate Arena Monitor */}
          <Panel defaultSize="45%" minSize="30%" className="flex flex-col gap-6 px-3 min-h-0">
            <MADEngineArena />
          </Panel>
          
          <Separator className="w-1.5 rounded-full bg-slate-800/50 hover:bg-indigo-500/50 transition-colors mx-1 cursor-col-resize" />
          
          {/* Right column - Consensus, Scores, and Document Synthesizer */}
          <Panel defaultSize="30%" minSize="20%" maxSize="50%" className="flex flex-col pl-3 min-h-0">
            <Group orientation="vertical" className="h-full">
              <Panel defaultSize="35%" minSize="15%" className="flex flex-col pb-3 min-h-0 overflow-y-auto">
                <MADEngineConsensus />
              </Panel>
              <Separator className="h-1.5 rounded-full bg-slate-800/50 hover:bg-indigo-500/50 transition-colors my-1 cursor-row-resize shrink-0" />
              <Panel defaultSize="65%" minSize="25%" className="flex flex-col pt-3 min-h-0 overflow-hidden">
                <MADEngineBlueprints />
              </Panel>
            </Group>
          </Panel>
          
        </Group>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <MADEngineProvider>
      <MADEngineLayout />
    </MADEngineProvider>
  );
}

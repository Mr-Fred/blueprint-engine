"use client";

import React, { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import {
  Network,
  Code,
  Eye,
  AlertTriangle,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Minimize2,
  Move,
} from "lucide-react";

interface MermaidViewerProps {
  chart: string;
  filename?: string;
}

/**
 * Normalizes hardcoded light/pastel classDef fills in .mmd diagrams to rich dark-mode
 * enterprise palettes with explicit high-contrast readable text colors.
 */
function normalizeMermaidContrast(rawChart: string): string {
  let text = rawChart
    .replace(/^```mermaid\s*/i, "")
    .replace(/^```\s*/, "")
    .replace(/```\s*$/, "")
    .trim();

  // Replace common pastel fill classDefs with high-contrast dark-theme equivalents
  text = text.replace(/classDef\s+(\w+)\s+fill:#dfd[^;\n]*/gi, "classDef $1 fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5");
  text = text.replace(/classDef\s+(\w+)\s+fill:#fdd[^;\n]*/gi, "classDef $1 fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff7ed");
  text = text.replace(/classDef\s+(\w+)\s+fill:#bbf[^;\n]*/gi, "classDef $1 fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#eff6ff");
  text = text.replace(/classDef\s+(\w+)\s+fill:#f9f[^;\n]*/gi, "classDef $1 fill:#581c87,stroke:#a855f7,stroke-width:2px,color:#faf5ff");
  text = text.replace(/classDef\s+(\w+)\s+fill:#ff9[^;\n]*/gi, "classDef $1 fill:#713f12,stroke:#eab308,stroke-width:2px,color:#fef08a");

  // Catch any remaining light pastel fills and enforce dark slate text color
  text = text.replace(/(classDef\s+\w+\s+[^;\n]*fill:#[d-fD-F][0-9a-fA-F]{2,5}[^;\n]*?)(;|\n|$)/gi, (match, prefix, suffix) => {
    if (!prefix.includes("color:")) {
      return `${prefix},color:#0f172a${suffix}`;
    }
    return match;
  });

  return text;
}

export default function MermaidViewer({ chart, filename = "diagrams/topology.mmd" }: MermaidViewerProps) {
  const [viewMode, setViewMode] = useState<"visual" | "code">("visual");
  const [svgContent, setSvgContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Zoom & Pan interactive state
  const [zoom, setZoom] = useState<number>(1);
  const [position, setPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const idRef = useRef(`mermaid-${Math.random().toString(36).substring(2, 9)}`);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function renderDiagram() {
      try {
        setError(null);
        const cleaned = normalizeMermaidContrast(chart);

        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "base",
          themeVariables: {
            darkMode: true,
            background: "#090d16",
            primaryColor: "#1e1b4b",
            primaryTextColor: "#f8fafc",
            primaryBorderColor: "#6366f1",
            lineColor: "#818cf8",
            secondaryColor: "#0f172a",
            tertiaryColor: "#1e293b",
            clusterBkg: "#0f172a",
            clusterBorder: "#334155",
            edgeLabelBackground: "#0f172a",
            nodeBorder: "#6366f1",
            fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
            fontSize: "14px",
          },
          securityLevel: "loose",
        });

        const { svg } = await mermaid.render(idRef.current, cleaned);
        if (isMounted) {
          let enhancedSvg = svg
            .replace(/max-width:\s*[\d.]+px;?/gi, "")
            .replace(/height:\s*100%;?/gi, "");

          // Inject global high-contrast font styling for all node text labels
          enhancedSvg = enhancedSvg.replace(
            /<style>/i,
            `<style>\n.nodeLabel, .label text, .node text, tspan { font-weight: 600 !important; font-size: 13.5px !important; }\n`
          );

          setSvgContent(enhancedSvg);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || "Failed to render Mermaid diagram.");
        }
      }
    }
    if (chart) {
      renderDiagram();
    }
    return () => {
      isMounted = false;
    };
  }, [chart]);

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.2, 4));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.2, 0.3));
  const handleResetZoom = () => {
    setZoom(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (viewMode !== "visual" || !svgContent) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 0.1 : -0.1;
    setZoom((prev) => Math.min(Math.max(prev + zoomFactor, 0.3), 4));
  };

  const renderCanvas = (isOverlay = false) => (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      className={`relative rounded-xl overflow-hidden border border-slate-800 bg-[#090d16] flex flex-col items-center justify-center select-none ${
        isOverlay
          ? "w-full h-full rounded-none border-0"
          : "min-h-[500px] max-h-[680px] w-full"
      } ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
    >
      {/* Floating Interactive Zoom Toolbar */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1.5 bg-slate-900/95 border border-slate-700/80 rounded-xl px-2.5 py-1.5 shadow-xl backdrop-blur-md">
        <button
          onClick={handleZoomOut}
          title="Zoom Out (-20%)"
          className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition"
        >
          <ZoomOut className="w-4 h-4" />
        </button>

        <span className="text-xs font-mono font-bold text-indigo-300 min-w-[48px] text-center">
          {Math.round(zoom * 100)}%
        </span>

        <button
          onClick={handleZoomIn}
          title="Zoom In (+20%)"
          className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition"
        >
          <ZoomIn className="w-4 h-4" />
        </button>

        <div className="w-px h-4 bg-slate-700 mx-1" />

        <button
          onClick={handleResetZoom}
          title="Reset Zoom & Center (100%)"
          className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        <div className="w-px h-4 bg-slate-700 mx-1" />

        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          title={isFullscreen ? "Exit Fullscreen" : "Fullscreen View"}
          className="p-1.5 rounded-lg hover:bg-slate-800 text-indigo-400 hover:text-indigo-300 transition"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* Pan instruction tooltip badge */}
      <div className="absolute bottom-4 left-4 z-20 flex items-center gap-1.5 bg-slate-900/80 border border-slate-800 rounded-lg px-2.5 py-1 text-[11px] text-slate-400 pointer-events-none">
        <Move className="w-3.5 h-3.5 text-indigo-400" />
        <span>Scroll to zoom · Drag to pan</span>
      </div>

      {error ? (
        <div className="flex flex-col items-center text-center max-w-md space-y-3 p-4">
          <AlertTriangle className="w-8 h-8 text-amber-400" />
          <div className="text-xs font-semibold text-amber-300">Could not render visual diagram</div>
          <p className="text-[11px] text-slate-400 font-mono">{error}</p>
          <button
            onClick={() => setViewMode("code")}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white rounded-lg transition"
          >
            View Mermaid Code
          </button>
        </div>
      ) : svgContent ? (
        <div
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.15s ease-out",
          }}
          className="p-8 flex items-center justify-center w-full"
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
      ) : (
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          Rendering interactive diagram...
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <Network className="w-5 h-5 text-indigo-400" />
          <div>
            <h4 className="text-xs font-bold text-white">Mermaid System Topology Architecture</h4>
            <p className="text-[10px] text-slate-400">
              High-contrast visual topology · Mouse scroll zooms · Click & drag pans across diagram.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode("visual")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === "visual"
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-800"
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            Visual Diagram
          </button>
          <button
            onClick={() => setViewMode("code")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === "code"
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-800"
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            Mermaid Code
          </button>
        </div>
      </div>

      {viewMode === "visual" ? (
        renderCanvas(false)
      ) : (
        <div className="rounded-xl overflow-hidden border border-slate-800 bg-slate-950">
          <div className="bg-slate-900 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>{filename}</span>
            <span className="text-indigo-400">Mermaid Graph Syntax</span>
          </div>
          <pre className="p-4 overflow-x-auto text-xs font-mono leading-relaxed text-indigo-200">
            <code>{chart}</code>
          </pre>
        </div>
      )}

      {/* Fullscreen Overlay Portal */}
      {isFullscreen &&
        typeof document !== "undefined" &&
        createPortal(
          <div className="fixed inset-0 z-50 bg-[#090d16] flex flex-col">
            <div className="bg-slate-900/95 border-b border-slate-800 px-6 py-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Network className="w-5 h-5 text-indigo-400" />
                <span className="text-sm font-bold text-white">Architecture Topology Fullscreen Explorer</span>
                <span className="text-xs text-slate-400 font-mono">({filename})</span>
              </div>
              <button
                onClick={() => setIsFullscreen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition flex items-center gap-1.5"
              >
                <Minimize2 className="w-4 h-4" /> Close Fullscreen
              </button>
            </div>
            <div className="flex-1 w-full relative overflow-hidden">{renderCanvas(true)}</div>
          </div>,
          document.body
        )}
    </div>
  );
}

"use client";

import React, { useState, useEffect } from "react";
import { Activity, RefreshCw, X, Clock, Shield, Cpu, Award } from "lucide-react";

interface OTelSpan {
  span_id: string;
  trace_id: string;
  name: string;
  attributes: Record<string, any>;
  start_time_ns?: number;
  end_time_ns?: number;
}

interface TraceInspectorModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const TraceInspectorModal: React.FC<TraceInspectorModalProps> = ({
  projectId,
  isOpen,
  onClose,
}) => {
  const [spans, setSpans] = useState<OTelSpan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTraces = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/projects/${projectId}/trace`);
      if (!res.ok) {
        throw new Error(`Failed to fetch traces (${res.status})`);
      }
      const data = await res.json();
      setSpans(data.otel_spans || data.spans || []);
    } catch (err: any) {
      setError(err.message || "Error loading OpenTelemetry traces");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchTraces();
    }
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  const getRoleBadge = (role?: string) => {
    if (!role) return <span className="text-xs text-slate-400">System</span>;
    if (role.toLowerCase().includes("security")) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/20">
          <Shield className="w-3 h-3" /> {role}
        </span>
      );
    }
    if (role.toLowerCase().includes("sre")) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
          <Activity className="w-3 h-3" /> {role}
        </span>
      );
    }
    if (role.toLowerCase().includes("judge")) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
          <Award className="w-3 h-3" /> {role}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
        <Cpu className="w-3 h-3" /> {role}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <Activity className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-slate-100">
              OpenTelemetry Live Trace Inspector
            </h2>
            <span className="text-xs bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-2 py-0.5 rounded font-mono">
              {projectId}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchTraces}
              disabled={loading}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition flex items-center gap-1.5 text-xs font-medium disabled:opacity-50"
              title="Refresh Traces"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
              {error}
            </div>
          )}

          {loading && spans.length === 0 && (
            <div className="text-center py-12 text-slate-400 text-sm">
              Loading OpenTelemetry spans...
            </div>
          )}

          {!loading && spans.length === 0 && !error && (
            <div className="text-center py-12 text-slate-500 text-sm">
              No OpenTelemetry spans recorded for this project yet. Start a debate turn to capture trace milestones.
            </div>
          )}

          {spans.map((span, idx) => {
            const role = span.attributes?.agent_role || (span as any).agent_role;
            const duration = span.attributes?.duration_ms || (span as any).duration_ms;
            const round = span.attributes?.round_number ?? (span as any).round_number;

            return (
              <div
                key={idx}
                className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 space-y-3 hover:border-indigo-500/30 transition"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-indigo-300 font-mono">
                      {span.name || (span as any).span_name || "SPAN"}
                    </span>
                    {getRoleBadge(role)}
                    {round !== undefined && (
                      <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                        Round #{round}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                    {duration !== undefined && (
                      <span className="flex items-center gap-1 text-emerald-400">
                        <Clock className="w-3.5 h-3.5" />
                        {Number(duration).toFixed(1)}ms
                      </span>
                    )}
                    <span className="text-slate-500">span:{span.span_id}</span>
                  </div>
                </div>

                {/* GenAI Telemetry Highlights */}
                {span.attributes && (
                  <div className="flex items-center flex-wrap gap-2 pt-1">
                    {span.attributes["gen_ai.system"] && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                        {String(span.attributes["gen_ai.system"]).toUpperCase()} GENAI
                      </span>
                    )}
                    {(span.attributes["gen_ai.usage.prompt_tokens"] || span.attributes["llm.prompt_tokens"]) ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-300 border border-blue-500/20">
                        Prompt: {String(span.attributes["gen_ai.usage.prompt_tokens"] || span.attributes["llm.prompt_tokens"])} tokens
                      </span>
                    ) : null}
                    {(span.attributes["gen_ai.usage.completion_tokens"] || span.attributes["llm.completion_tokens"]) ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
                        Completion: {String(span.attributes["gen_ai.usage.completion_tokens"] || span.attributes["llm.completion_tokens"])} tokens
                      </span>
                    ) : (span.attributes["metadata.critique_chars"] || span.attributes["metadata.proposal_chars"]) ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
                        Est. Output: ~{Math.round(Number(span.attributes["metadata.critique_chars"] || span.attributes["metadata.proposal_chars"]) / 4)} tokens ({String(span.attributes["metadata.critique_chars"] || span.attributes["metadata.proposal_chars"])} chars)
                      </span>
                    ) : null}
                    {(span.attributes["gen_ai.usage.total_tokens"] || span.attributes["llm.total_tokens"]) ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-semibold">
                        Total: {String(span.attributes["gen_ai.usage.total_tokens"] || span.attributes["llm.total_tokens"])} tokens
                      </span>
                    ) : null}
                  </div>
                )}

                {/* Attributes Table */}
                {Object.keys(span.attributes || {}).length > 0 && (
                  <div className="bg-slate-900/80 rounded-lg p-2.5 border border-slate-800/60 overflow-x-auto">
                    <table className="w-full text-[11px] text-left">
                      <thead>
                        <tr className="text-slate-400 border-b border-slate-800">
                          <th className="pb-1 font-semibold">Attribute Key</th>
                          <th className="pb-1 font-semibold">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/50">
                        {Object.entries(span.attributes).map(([k, v], i) => (
                          <tr key={i}>
                            <td className="py-1 pr-4 font-mono text-indigo-300 whitespace-nowrap">
                              {k}
                            </td>
                            <td className="py-1 font-mono text-slate-300 break-all">
                              {typeof v === "object" ? JSON.stringify(v) : String(v)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center text-xs text-slate-400">
          <span>Total Recorded Spans: {spans.length}</span>
          <span className="font-mono text-slate-500">Native ADK OpenTelemetry SDK</span>
        </div>
      </div>
    </div>
  );
};

"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Terminal, AlertCircle, Copy, Check } from "lucide-react";
import type { RagTraceEvent } from "@/lib/stream";
import { cn } from "@/lib/utils";

const STAGE_LABELS: Record<string, string> = {
  query_rewrite: "Query 改写",
  embedding: "向量化",
  retrieval: "检索召回",
  rerank: "重排序 (Rerank)",
  citations: "引用提取",
  terminal_error: "终止错误",
};

export function RagTracePanel({ events }: { events: RagTraceEvent[] }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  if (!events || events.length === 0) return null;

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-[#e2e8f0] bg-[#f8fafc] dark:border-[#334155] dark:bg-[#1e293b]/50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold text-[#64748b] transition-colors hover:bg-[#f1f5f9] dark:text-[#94a3b8] dark:hover:bg-[#334155]"
      >
        <div className="flex items-center gap-2">
          <Terminal className="size-3.5" />
          <span>RAG 执行链路追踪 (Debug)</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard.writeText(JSON.stringify(events, null, 2));
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
            className="flex items-center gap-1 rounded bg-[#ffffff] dark:bg-[#1e293b] px-2 py-0.5 text-[10px] text-[#64748b] hover:bg-[#e2e8f0] dark:text-[#94a3b8] dark:hover:bg-[#475569] border border-[#e2e8f0] dark:border-[#475569] transition-all font-normal shadow-sm hover:shadow active:scale-95"
          >
            {copied ? (
              <>
                <Check className="size-3 text-emerald-600 dark:text-emerald-400" />
                <span className="text-emerald-600 dark:text-emerald-400">已复制</span>
              </>
            ) : (
              <>
                <Copy className="size-3" />
                <span>复制 JSON</span>
              </>
            )}
          </span>
          {isExpanded ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="divide-y divide-[#e2e8f0] border-t border-[#e2e8f0] dark:divide-[#334155] dark:border-[#334155]">
          {events.map((event, idx) => {
            const isError = event.stage === "terminal_error";
            const duration = Object.entries(event.data).find(([key]) =>
              key.endsWith("_duration_ms"),
            )?.[1] as number | undefined;
            
            const isNoCandidates = event.stage === "rerank" && event.data.rerank_candidates_count === 0;

            return (
              <div
                key={idx}
                className={cn(
                  "px-3 py-2 text-[11px] leading-relaxed",
                  isError ? "bg-rose-50 dark:bg-rose-900/20" : ""
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-medium">
                    <span
                      className={cn(
                        isError ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"
                      )}
                    >
                      {STAGE_LABELS[event.stage] || event.stage}
                    </span>
                    {isNoCandidates && (
                      <span className="flex items-center gap-0.5 text-amber-500">
                        <AlertCircle className="size-3" />
                        <span>无候选</span>
                      </span>
                    )}
                  </div>
                  {duration !== undefined && (
                    <span className="text-[#94a3b8]">{duration}ms</span>
                  )}
                </div>
                <div className="mt-1 font-mono text-[#475569] dark:text-[#94a3b8] break-all">
                  {JSON.stringify(event.data, null, 2)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { Trash2 } from "lucide-react";

import type { KnowledgeBaseListItem } from "@/services/knowledge";

import { KnowledgeStatusBadge } from "./knowledge-status-badge";

type KnowledgeCardProps = {
  item: KnowledgeBaseListItem;
  isDeleting: boolean;
  onDelete: (knowledgeBaseId: number) => void;
};

export function KnowledgeCard({ item, isDeleting, onDelete }: KnowledgeCardProps) {
  const isIndexing = item.status === "pending" || item.status === "processing";
  const createdDate = new Date(item.created_at).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="group relative flex flex-col gap-2.5 overflow-hidden rounded-xl border border-[rgba(148,163,184,0.24)] bg-white px-4 py-3 transition-colors hover:bg-[rgba(148,163,184,0.04)] dark:border-slate-700 dark:bg-[#2a2a2a] dark:hover:bg-[rgba(255,255,255,0.02)]">
      <div className="flex items-start justify-between gap-2">
        <p className="line-clamp-2 text-sm font-medium text-[#0f172a] dark:text-[#ececec]">
          {item.name || "未命名文档"}
        </p>
        <KnowledgeStatusBadge status={item.status} />
      </div>

      <a
        href={item.source_url}
        target="_blank"
        rel="noreferrer"
        title={item.source_url}
        className="block truncate text-xs text-[#64748b] underline decoration-[rgba(148,163,184,0.50)] underline-offset-2 hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:text-[#ececec]"
      >
        {item.source_url}
      </a>

      {item.error_message ? (
        <p className="text-xs text-rose-600 dark:text-rose-400">{item.error_message}</p>
      ) : null}

      <div className="flex items-center justify-between gap-2 border-t border-[rgba(148,163,184,0.16)] pt-2.5 dark:border-slate-700/60">
        <span className="text-xs text-[#64748b] dark:text-[#8e8ea0]">{createdDate}</span>
        {isIndexing ? (
          <span className="text-xs text-[#64748b] dark:text-[#8e8ea0]">索引中暂不可删除</span>
        ) : (
          <button
            type="button"
            disabled={isDeleting}
            onClick={() => onDelete(item.knowledge_base_id)}
            aria-label="删除"
            className="rounded-lg p-1.5 text-[#64748b] opacity-0 transition-all group-hover:opacity-100 hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-40 dark:text-[#8e8ea0] dark:hover:bg-rose-900/20 dark:hover:text-rose-400"
          >
            <Trash2 size={14} aria-hidden="true" />
          </button>
        )}
      </div>

      {isIndexing && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 overflow-hidden rounded-b-xl bg-[rgba(148,163,184,0.12)]">
          <div className="h-full w-1/2 animate-pulse bg-[#2f6df6]/40 dark:bg-[#4f8ef7]/40" />
        </div>
      )}
    </div>
  );
}

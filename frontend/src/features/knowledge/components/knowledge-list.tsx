import type { KnowledgeBaseListItem } from "@/services/knowledge";

import type { KnowledgeTab } from "../hooks/use-knowledge-base";
import { KnowledgeCard } from "./knowledge-card";

type KnowledgeListProps = {
  items: KnowledgeBaseListItem[];
  isLoading: boolean;
  errorMessage: string | null;
  deletingKnowledgeBaseId: number | null;
  activeTab: KnowledgeTab;
  onDelete: (knowledgeBaseId: number) => void;
  onRetry: () => void;
};

const emptyMessages: Record<KnowledgeTab, { title: string; desc: string }> = {
  all: {
    title: "还没有知识库",
    desc: "点击右上角「+ 添加」导入第一个知识库。",
  },
  indexing: {
    title: "没有处理中的知识库",
    desc: "所有知识库都已完成索引。",
  },
  done: {
    title: "没有已完成的知识库",
    desc: "导入知识库后，索引完成的文档会出现在这里。",
  },
  failed: {
    title: "没有失败的知识库",
    desc: "太好了，所有知识库都运行正常！",
  },
};

export function KnowledgeList({
  items,
  isLoading,
  errorMessage,
  deletingKnowledgeBaseId,
  activeTab,
  onDelete,
  onRetry,
}: KnowledgeListProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-32 animate-pulse rounded-xl border border-[rgba(148,163,184,0.24)] bg-white dark:border-slate-700 dark:bg-[#2a2a2a]"
          />
        ))}
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 dark:border-rose-800/50 dark:bg-rose-900/20">
        <p className="text-sm font-medium text-rose-900 dark:text-rose-300">加载知识库失败</p>
        <p className="mt-1 text-sm text-rose-700 dark:text-rose-400">{errorMessage}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 text-sm font-medium text-rose-900 underline underline-offset-4 dark:text-rose-300"
        >
          重试
        </button>
      </div>
    );
  }

  if (items.length === 0) {
    const { title, desc } = emptyMessages[activeTab];
    return (
      <div className="rounded-xl border border-dashed border-[rgba(148,163,184,0.40)] bg-white p-8 text-center dark:border-slate-700 dark:bg-[#2a2a2a]">
        <p className="text-sm font-medium text-[#0f172a] dark:text-[#ececec]">{title}</p>
        <p className="mt-1 text-sm text-[#64748b] dark:text-[#8e8ea0]">{desc}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <KnowledgeCard
          key={item.knowledge_base_id}
          item={item}
          isDeleting={deletingKnowledgeBaseId === item.knowledge_base_id}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

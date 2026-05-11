import { Button } from "@/components/ui/button";
import type { KnowledgeBaseListItem } from "@/services/knowledge";

import { KnowledgeStatusBadge } from "./knowledge-status-badge";

type KnowledgeListProps = {
  items: KnowledgeBaseListItem[];
  isLoading: boolean;
  errorMessage: string | null;
  deletingKnowledgeBaseId: number | null;
  onDelete: (knowledgeBaseId: number) => void;
  onRetry: () => void;
};

export function KnowledgeList({
  items,
  isLoading,
  errorMessage,
  deletingKnowledgeBaseId,
  onDelete,
  onRetry,
}: KnowledgeListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-4 sm:p-6 lg:p-8">
        {[0, 1, 2].map((item) => (
          <div
            key={item}
            className="h-20 animate-pulse rounded-lg border border-slate-200 bg-white"
          />
        ))}
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="p-4 sm:p-6 lg:p-8">
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4">
          <p className="text-sm font-medium text-rose-900">加载知识库失败</p>
          <p className="mt-1 text-sm text-rose-700">{errorMessage}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 text-sm font-medium text-rose-900 underline underline-offset-4"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="p-4 sm:p-6 lg:p-8">
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6">
          <p className="text-sm font-medium text-slate-950">还没有知识库</p>
          <p className="mt-1 text-sm text-slate-600">
            先粘贴一个技术文档 URL，系统会异步爬取并建立可引用的知识库。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-4 border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
          <span>知识库</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        <ul className="divide-y divide-slate-200">
          {items.map((item) => (
            <li
              key={item.knowledge_base_id}
              className="grid gap-3 px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-start"
            >
              <div className="min-w-0">
                <p className="font-medium text-slate-950">
                  {item.name || "未命名文档"}
                </p>
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noreferrer"
                  title={item.source_url}
                  className="mt-1 block break-all text-sm text-slate-600 underline decoration-slate-300 underline-offset-4 hover:text-slate-950"
                >
                  {item.source_url}
                </a>
                {item.error_message ? (
                  <p className="mt-2 text-sm text-rose-700">
                    {item.error_message}
                  </p>
                ) : null}
              </div>
              <KnowledgeStatusBadge status={item.status} />
              <div className="flex flex-col items-start gap-2 md:items-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={
                    item.status === "pending" ||
                    item.status === "processing" ||
                    deletingKnowledgeBaseId === item.knowledge_base_id
                  }
                  onClick={() => onDelete(item.knowledge_base_id)}
                >
                  {deletingKnowledgeBaseId === item.knowledge_base_id ? "删除中..." : "删除"}
                </Button>
                {item.status === "pending" || item.status === "processing" ? (
                  <p className="text-xs text-slate-500">索引中暂不可删除</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

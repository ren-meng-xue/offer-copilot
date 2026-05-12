import type { KnowledgeStatus } from "@/services/knowledge";

const statusMeta: Record<
  KnowledgeStatus,
  { dot: string; text: string; label: string }
> = {
  pending: {
    dot: "bg-amber-400",
    text: "等待中",
    label:
      "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800/50 dark:bg-amber-900/20 dark:text-amber-300",
  },
  processing: {
    dot: "bg-blue-500 animate-pulse",
    text: "处理中",
    label:
      "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-800/50 dark:bg-sky-900/20 dark:text-sky-300",
  },
  done: {
    dot: "bg-emerald-500",
    text: "已完成",
    label:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800/50 dark:bg-emerald-900/20 dark:text-emerald-300",
  },
  failed: {
    dot: "bg-rose-500",
    text: "失败",
    label:
      "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-800/50 dark:bg-rose-900/20 dark:text-rose-300",
  },
};

type KnowledgeStatusBadgeProps = {
  status: KnowledgeStatus;
};

export function KnowledgeStatusBadge({ status }: KnowledgeStatusBadgeProps) {
  const meta = statusMeta[status];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${meta.label}`}
    >
      <span className={`size-1.5 shrink-0 rounded-full ${meta.dot}`} aria-hidden="true" />
      {meta.text}
    </span>
  );
}

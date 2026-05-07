import type { KnowledgeStatus } from "@/services/knowledge";

const statusMeta: Record<
  KnowledgeStatus,
  { label: string; className: string; indicator: string }
> = {
  pending: {
    label: "pending",
    className: "border-amber-200 bg-amber-50 text-amber-800",
    indicator: "排队",
  },
  processing: {
    label: "processing",
    className: "border-sky-200 bg-sky-50 text-sky-800",
    indicator: "索引",
  },
  done: {
    label: "done",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
    indicator: "可问",
  },
  failed: {
    label: "failed",
    className: "border-rose-200 bg-rose-50 text-rose-800",
    indicator: "失败",
  },
};

type KnowledgeStatusBadgeProps = {
  status: KnowledgeStatus;
};

export function KnowledgeStatusBadge({ status }: KnowledgeStatusBadgeProps) {
  const meta = statusMeta[status];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium ${meta.className}`}
    >
      <span aria-hidden="true">{meta.indicator}</span>
      <span>{meta.label}</span>
    </span>
  );
}

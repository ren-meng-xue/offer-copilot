import type { KnowledgeTab } from "../hooks/use-knowledge-base";

type Counts = {
  all: number;
  indexing: number;
  done: number;
  failed: number;
};

type KnowledgeFilterTabsProps = {
  activeTab: KnowledgeTab;
  counts: Counts;
  searchQuery: string;
  onTabChange: (tab: KnowledgeTab) => void;
  onSearchChange: (query: string) => void;
};

const TABS: { id: KnowledgeTab; label: string; countKey: keyof Counts }[] = [
  { id: "all", label: "全部", countKey: "all" },
  { id: "indexing", label: "处理中", countKey: "indexing" },
  { id: "done", label: "已完成", countKey: "done" },
  { id: "failed", label: "失败", countKey: "failed" },
];

export function KnowledgeFilterTabs({
  activeTab,
  counts,
  searchQuery,
  onTabChange,
  onSearchChange,
}: KnowledgeFilterTabsProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1">
        {TABS.map(({ id, label, countKey }) => {
          const count = counts[countKey];
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onTabChange(id)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-[#2f6df6] text-white dark:bg-[#4f8ef7]"
                  : "text-[#64748b] hover:bg-[rgba(148,163,184,0.12)] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-[rgba(255,255,255,0.06)] dark:hover:text-[#ececec]"
              }`}
            >
              {label}
              {count > 0 || id === "all" ? (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-xs font-medium tabular-nums ${
                    isActive
                      ? "bg-white/20 text-white"
                      : "bg-[rgba(148,163,184,0.16)] text-[#64748b] dark:bg-[rgba(255,255,255,0.08)] dark:text-[#8e8ea0]"
                  }`}
                >
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-[#64748b] dark:text-[#8e8ea0]">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </span>
        <input
          id="knowledge-search"
          aria-label="搜索知识库"
          className="w-full rounded-xl border border-[rgba(148,163,184,0.32)] bg-white py-2 pl-8 pr-3 text-sm text-[#0f172a] outline-none placeholder:text-[#64748b] focus:border-[#2f6df6]/50 focus:ring-2 focus:ring-[#2f6df6]/20 dark:border-slate-700 dark:bg-[#2a2a2a] dark:text-[#ececec] dark:placeholder:text-[#8e8ea0] dark:focus:border-[#4f8ef7]/50 dark:focus:ring-[#4f8ef7]/20"
          placeholder="按名称或 URL 搜索"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>
    </div>
  );
}

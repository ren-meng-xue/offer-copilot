import type { Citation } from "@/lib/stream";

type CitationListProps = {
  citations: Citation[];
};

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return null;
  }

  const handleCitationClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    window.dispatchEvent(
      new CustomEvent("active-citations-updated", { detail: citations }),
    );
    window.dispatchEvent(new CustomEvent("open-citation-panel"));
  };

  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {citations.map((citation) => (
        <a
          key={`${citation.index}-${citation.chunk_id}`}
          href={citation.source_url}
          target="_blank"
          rel="noreferrer"
          title={citation.source_url}
          onClick={handleCitationClick}
          className="inline-flex items-center gap-1 rounded-full border border-[rgba(148,163,184,0.32)] bg-white px-2 py-0.5 text-xs text-[#64748b] transition-colors hover:border-[#2f6df6]/40 hover:text-[#2f6df6] dark:border-[rgba(51,65,85,0.60)] dark:bg-[#2f2f2f] dark:text-[#8e8ea0] dark:hover:border-[#4f8ef7]/40 dark:hover:text-[#4f8ef7]"
        >
          <span className="font-medium">[{citation.index}]</span>
          <span className="max-w-[160px] truncate">
            {formatCitationTitle(citation)}
          </span>
        </a>
      ))}
    </div>
  );
}

export function CitationPanel({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2 p-3">
      {citations.map((citation) => (
        <a
          key={`${citation.index}-${citation.chunk_id}`}
          href={citation.source_url}
          target="_blank"
          rel="noreferrer"
          className="block rounded-xl border border-[rgba(148,163,184,0.24)] bg-white p-3 text-sm shadow-sm transition-transform hover:-translate-y-0.5 dark:border-slate-700 dark:bg-[#2f2f2f]"
        >
          <p className="truncate font-medium text-[#0f172a] dark:text-[#ececec]">
            [{citation.index}] {formatCitationTitle(citation)}
          </p>
          <p className="mt-1 truncate text-xs text-[#64748b] dark:text-[#8e8ea0]">
            {citation.source_url}
          </p>
          {citation.snippet ? (
            <p className="mt-2 line-clamp-2 text-xs text-[#64748b] dark:text-[#8e8ea0]">
              {citation.snippet}
            </p>
          ) : null}
        </a>
      ))}
    </div>
  );
}

function formatCitationTitle(citation: Citation) {
  if (citation.knowledge_base_name && citation.heading_path) {
    return `${citation.knowledge_base_name} / ${citation.heading_path}`;
  }

  return citation.knowledge_base_name || citation.heading_path || "Source";
}

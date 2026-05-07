import type { Citation } from "@/lib/stream";

type CitationListProps = {
  citations: Citation[];
};

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 space-y-2">
      {citations.map((citation) => (
        <a
          key={`${citation.index}-${citation.chunk_id}`}
          href={citation.source_url}
          target="_blank"
          rel="noreferrer"
          title={citation.source_url}
          className="block rounded-md border border-slate-200 bg-white p-3 text-sm transition-colors hover:border-slate-300 hover:bg-slate-50"
        >
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium text-slate-950">
              [{citation.index}] {citation.heading_path || "Source"}
            </span>
            <span className="truncate text-xs text-slate-500">
              {citation.source_url}
            </span>
          </div>
          <p className="mt-2 line-clamp-3 text-slate-600">
            {citation.snippet}
          </p>
        </a>
      ))}
    </div>
  );
}

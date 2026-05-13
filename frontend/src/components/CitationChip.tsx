import type { Citation } from "../types";

interface Props {
  citation: Citation;
  onClick: (citation: Citation) => void;
}

export function CitationChip({ citation, onClick }: Props) {
  const label = `${citation.source.replace(/\.pdf$/i, "")} p.${citation.page}`;
  return (
    <button
      onClick={() => onClick(citation)}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/60 transition-colors"
      title={citation.text}
    >
      [{citation.id}] {label}
    </button>
  );
}
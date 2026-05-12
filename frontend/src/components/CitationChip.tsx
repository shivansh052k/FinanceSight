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
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
      title={citation.text}
    >
      [{citation.id}] {label}
    </button>
  );
}
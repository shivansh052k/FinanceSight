import type { Document } from "../types";

interface Props {
  documents: Document[];
  totalChunks: number;
  onRemove: (filename: string) => void;
}

const statusConfig: Record<string, { dot: string; label: string }> = {
  complete:   { dot: "bg-green-500",  label: "Ready" },
  processing: { dot: "bg-yellow-400 animate-pulse", label: "Processing" },
  error:      { dot: "bg-red-500",    label: "Error" },
};

export function DocumentList({ documents, totalChunks, onRemove }: Props) {
  if (documents.length === 0) {
    return (
      <p className="text-xs text-zinc-400 text-center py-6 px-2">
        No documents yet. Upload PDFs to get started.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {documents.map((doc) => {
        const cfg = statusConfig[doc.status] ?? { dot: "bg-zinc-400", label: doc.status };
        return (
          <div
            key={doc.filename}
            className="group flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-zinc-100 transition-colors"
          >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dot}`} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-zinc-800 truncate" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-[10px] text-zinc-400">{cfg.label}</p>
            </div>
            {doc.status === "complete" && (
              <button
                onClick={() => onRemove(doc.filename)}
                className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-500 transition-all text-xs shrink-0"
                title="Remove"
              >
                ✕
              </button>
            )}
          </div>
        );
      })}
      <p className="text-[10px] text-zinc-400 px-2 pt-1">
        {totalChunks.toLocaleString()} chunks indexed
      </p>
    </div>
  );
}
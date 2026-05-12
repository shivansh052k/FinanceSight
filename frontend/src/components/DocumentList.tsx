import type { Document } from "../types";

interface Props {
  documents: Document[];
  totalChunks: number;
}

const statusStyles: Record<string, string> = {
  complete: "bg-green-100 text-green-800",
  processing: "bg-yellow-100 text-yellow-800",
  error: "bg-red-100 text-red-800",
};

export function DocumentList({ documents, totalChunks }: Props) {
  if (documents.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-4">No documents ingested yet.</p>;
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div key={doc.filename} className="flex items-center justify-between px-3 py-2 rounded-lg border border-gray-200 bg-white">
          <span className="text-sm text-gray-800 truncate max-w-[70%]" title={doc.filename}>
            {doc.filename}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusStyles[doc.status] ?? "bg-gray-100 text-gray-600"}`}>
            {doc.status === "processing" ? "⏳ processing" : doc.status}
          </span>
        </div>
      ))}
      <p className="text-xs text-gray-400 text-right pt-1">{totalChunks.toLocaleString()} total chunks</p>
    </div>
  );
}
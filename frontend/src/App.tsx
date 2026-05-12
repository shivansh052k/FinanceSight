import { useState, useRef, useCallback } from "react";
import { useChat } from "./hooks/useChat";
import { useDocuments } from "./hooks/useDocuments";
import { usePDFViewer } from "./hooks/usePDFViewer";
import { ChatPane } from "./components/ChatPane";
import { PDFViewer } from "./components/PDFViewer";
import { UploadModal } from "./components/UploadModal";
import { DocumentList } from "./components/DocumentList";
import type { Citation } from "./types";

export default function App() {
  const { messages, loading, error, sendMessage } = useChat();
  const { documents, totalChunks, uploading, upload, remove } = useDocuments();
  const { open: pdfOpen, filename, page, activeCitation, openCitation, goToPage, close: closePdf } = usePDFViewer();
  const [showUpload, setShowUpload] = useState(false);
  const [splitPercent, setSplitPercent] = useState(50);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setSplitPercent(Math.min(Math.max(pct, 25), 75));
  }, []);

  const stopDrag = useCallback(() => { isDragging.current = false; }, []);

  const handleUpload = (files: File[]) => {
    upload(files);
    setShowUpload(false);
  };

  const completeCount = documents.filter(d => d.status === "complete").length;

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      <aside className="w-64 flex flex-col bg-zinc-50 border-r border-zinc-200 shrink-0">
        <div className="px-4 py-4 border-b border-zinc-200">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
              <span className="text-white text-[10px] font-bold">FS</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-zinc-900 leading-none">FinanceSight</h1>
              <p className="text-[10px] text-zinc-400 mt-0.5">SEC 10-K Q&A</p>
            </div>
          </div>
        </div>

        <div className="px-3 pt-3 pb-1">
          <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider px-1 mb-1">
            Documents · {completeCount} ready
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-3">
          <DocumentList documents={documents} totalChunks={totalChunks} onRemove={remove} />
        </div>

        <div className="p-3 border-t border-zinc-200 space-y-1">
          <button
            onClick={() => setShowUpload(true)}
            className="w-full py-2 px-3 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            + Upload PDFs
          </button>
          {uploading && <p className="text-[10px] text-zinc-400 text-center">Ingesting files…</p>}
        </div>
      </aside>

      <div
        ref={containerRef}
        className="flex flex-1 overflow-hidden"
        onMouseMove={handleMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
      >
        <div style={{ width: pdfOpen ? `${splitPercent}%` : "100%" }} className="overflow-hidden">
          <ChatPane
            messages={messages}
            loading={loading}
            error={error}
            onSend={sendMessage}
            onCitationClick={openCitation}
          />
        </div>

        {pdfOpen && filename && (
          <>
            <div
              onMouseDown={() => { isDragging.current = true; }}
              className="w-1 bg-zinc-200 hover:bg-blue-400 active:bg-blue-500 cursor-col-resize transition-colors shrink-0"
            />
            <div style={{ width: `${100 - splitPercent}%` }} className="overflow-hidden">
              <PDFViewer
                filename={filename}
                page={page}
                activeCitation={activeCitation}
                onClose={closePdf}
                onPageChange={goToPage}
              />
            </div>
          </>
        )}
      </div>

      {showUpload && (
        <UploadModal onUpload={handleUpload} uploading={uploading} onClose={() => setShowUpload(false)} />
      )}
    </div>
  );
}
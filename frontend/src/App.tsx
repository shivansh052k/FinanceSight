import { useState } from "react";
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
  const { documents, totalChunks, uploading, upload } = useDocuments();
  const {
    open: pdfOpen, filename, page, activeCitation,
    openCitation, goToPage, close: closePdf,
  } = usePDFViewer();

  const [showUpload, setShowUpload] = useState(false);
  const [showDocs, setShowDocs] = useState(false);

  const handleCitationClick = (citation: Citation) => {
    openCitation(citation);
    setShowDocs(false);
  };

  const handleUpload = (files: File[]) => {
    upload(files);
    setShowUpload(false);
  };

  const completeCount = documents.filter((d) => d.status === "complete").length;

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200 shrink-0">
        <h1 className="text-base font-semibold text-gray-900">📊 FinanceSight</h1>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowDocs(true); setShowUpload(false); }}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Docs ({completeCount})
          </button>
          <button
            onClick={() => { setShowUpload(true); setShowDocs(false); }}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Upload
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className={pdfOpen ? "w-1/2 border-r border-gray-200" : "w-full"}>
          <ChatPane
            messages={messages}
            loading={loading}
            error={error}
            onSend={sendMessage}
            onCitationClick={handleCitationClick}
          />
        </div>

        {pdfOpen && filename && (
          <div className="w-1/2">
            <PDFViewer
              filename={filename}
              page={page}
              activeCitation={activeCitation}
              onClose={closePdf}
              onPageChange={goToPage}
            />
          </div>
        )}
      </div>

      {showUpload && (
        <UploadModal
          onUpload={handleUpload}
          uploading={uploading}
          onClose={() => setShowUpload(false)}
        />
      )}

      {showDocs && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-900">Ingested Documents</h2>
              <button
                onClick={() => setShowDocs(false)}
                className="text-gray-400 hover:text-gray-700 text-xl leading-none"
              >
                ✕
              </button>
            </div>
            <DocumentList documents={documents} totalChunks={totalChunks} />
          </div>
        </div>
      )}
    </div>
  );
}
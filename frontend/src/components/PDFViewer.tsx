import { useEffect, useRef } from "react";
import type { Citation } from "../types";
import * as pdfjsLib from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

interface Props {
  filename: string;
  page: number;
  activeCitation: Citation | null;
  onClose: () => void;
  onPageChange: (page: number) => void;
}

export function PDFViewer({ filename, page, activeCitation, onClose, onPageChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null);
  const pdfRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null);
  const totalPagesRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const pdf = await pdfjsLib.getDocument(
          `http://localhost:8000/pdfs/${encodeURIComponent(filename)}`
        ).promise;
        if (cancelled) { pdf.destroy(); return; }
        pdfRef.current = pdf;
        totalPagesRef.current = pdf.numPages;
      } catch (err) {
        console.error("PDF load failed:", err);
      }
    }

    pdfRef.current?.destroy();
    pdfRef.current = null;
    load();

    return () => { cancelled = true; };
  }, [filename]);

  useEffect(() => {
    async function render() {
      const pdf = pdfRef.current;
      const canvas = canvasRef.current;
      if (!pdf || !canvas) return;

      const safePage = Math.max(1, Math.min(page, pdf.numPages));

      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }

      try {
        const pdfPage = await pdf.getPage(safePage);
        const viewport = pdfPage.getViewport({ scale: 1.5 });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d")!;
        const task = pdfPage.render({ canvasContext: ctx, viewport });
        renderTaskRef.current = task;
        await task.promise;
      } catch (err: unknown) {
        if ((err as { name?: string }).name !== "RenderingCancelledException") {
          console.error("PDF render failed:", err);
        }
      }
    }

    render();
  }, [page, filename]);

  const total = totalPagesRef.current;

  return (
    <div className="flex flex-col h-full border-l border-gray-200">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
        <span className="text-sm font-medium text-gray-700 truncate max-w-[60%]" title={filename}>
          {filename}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
          >
            ◀
          </button>
          <span className="text-xs text-gray-600">
            {page}{total ? ` / ${total}` : ""}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={total > 0 && page >= total}
            className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
          >
            ▶
          </button>
          <button
            onClick={onClose}
            className="ml-2 text-gray-400 hover:text-gray-700 text-lg leading-none"
            aria-label="Close PDF viewer"
          >
            ✕
          </button>
        </div>
      </div>

      {activeCitation && (
        <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-200 text-xs text-amber-800 truncate">
          {activeCitation.text}
        </div>
      )}

      <div className="flex-1 overflow-auto bg-gray-100 flex justify-center p-4">
        <canvas ref={canvasRef} className="shadow-md" />
      </div>
    </div>
  );
}
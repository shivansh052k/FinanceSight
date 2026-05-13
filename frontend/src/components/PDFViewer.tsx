import { useEffect, useRef, useState } from "react";
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

const MIN_SCALE = 0.75;
const MAX_SCALE = 3.0;
const SCALE_STEP = 0.25;

export function PDFViewer({ filename, page, activeCitation, onClose, onPageChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null);
  const pdfRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null);
  const pageRef = useRef<pdfjsLib.PDFPageProxy | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1.5);
  const [pdfReady, setPdfReady] = useState(false);
  

  useEffect(() => {
    let cancelled = false;
    setPdfReady(false);
    setTotalPages(0);

    async function load() {
      pdfRef.current?.destroy();
      pdfRef.current = null;
      try {
        const pdf = await pdfjsLib.getDocument(
          `http://localhost:8000/pdfs/${encodeURIComponent(filename)}`
        ).promise;
        if (cancelled) { pdf.destroy(); return; }
        pdfRef.current = pdf;
        setTotalPages(pdf.numPages);
        setPdfReady(true);
      } catch (err) {
        console.error("PDF load failed:", err);
      }
    }

    load();
    return () => {
        cancelled = true;
        pageRef.current?.cleanup();
        pageRef.current = null;
    };
  }, [filename]);

  useEffect(() => {
    if (!pdfReady) return;

    async function render() {
      const pdf = pdfRef.current;
      const canvas = canvasRef.current;
      if (!pdf || !canvas) return;

      const safePage = Math.max(1, Math.min(page, pdf.numPages));

      if (renderTaskRef.current) {
          try { renderTaskRef.current.cancel(); } catch { /* already completed */ }
          renderTaskRef.current = null;
      }

      if (pageRef.current) {
          pageRef.current.cleanup();
          pageRef.current = null;
      }

      try {
        const pdfPage = await pdf.getPage(safePage);
        pageRef.current = pdfPage;
        const viewport = pdfPage.getViewport({ scale });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d")!;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
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
  }, [page, scale, pdfReady, filename]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-200 bg-zinc-50 shrink-0 dark:border-zinc-700 dark:bg-zinc-800 gap-2">
        <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300 truncate" title={filename}>
          {filename}
        </span>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => setScale(s => Math.max(MIN_SCALE, +(s - SCALE_STEP).toFixed(2)))} disabled={scale <= MIN_SCALE} className="px-2 py-1 text-xs rounded border border-zinc-300 hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-700 disabled:opacity-40">−</button>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 w-10 text-center">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale(s => Math.min(MAX_SCALE, +(s + SCALE_STEP).toFixed(2)))} disabled={scale >= MAX_SCALE} className="px-2 py-1 text-xs rounded border border-zinc-300 hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-700 disabled:opacity-40">+</button>
          <div className="w-px h-4 bg-zinc-200 mx-1" />
          <button onClick={() => onPageChange(page - 1)} disabled={page <= 1} className="px-2 py-1 text-xs rounded border border-zinc-300 hover:bg-zinc-100 disabled:opacity-40">◀</button>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 w-16 text-center">{page}{totalPages ? ` / ${totalPages}` : ""}</span>
          <button onClick={() => onPageChange(page + 1)} disabled={totalPages > 0 && page >= totalPages} className="px-2 py-1 text-xs rounded border border-zinc-300 hover:bg-zinc-100 disabled:opacity-40">▶</button>
          <div className="w-px h-4 bg-zinc-200 mx-1" />
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:text-zinc-500 dark:hover:text-zinc-200 text-sm px-1">✕</button>
        </div>
      </div>

      {activeCitation && (
        <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-200 text-xs text-amber-800 dark:bg-amber-900/20 dark:border-amber-800 dark:text-amber-400 line-clamp-2 shrink-0">
          {activeCitation.text}
        </div>
      )}

      <div className="flex-1 overflow-auto bg-zinc-100 dark:bg-zinc-900 flex justify-center p-4">
        {!pdfReady && (
          <div className="flex items-center justify-center h-full text-sm text-zinc-400 dark:text-zinc-600">Loading…</div>
        )}
        <canvas ref={canvasRef} className={`shadow-md ${!pdfReady ? "hidden" : ""}`} />
      </div>
    </div>
  );
}
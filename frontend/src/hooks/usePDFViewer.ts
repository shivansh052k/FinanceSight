import { useState, useCallback } from "react";
import type { Citation } from "../types";

export interface PDFViewerState {
  open: boolean;
  filename: string | null;
  page: number;
  activeCitation: Citation | null;
}

export function usePDFViewer() {
  const [state, setState] = useState<PDFViewerState>({
    open: false,
    filename: null,
    page: 1,
    activeCitation: null,
  });

  const openCitation = useCallback((citation: Citation) => {
    setState({
      open: true,
      filename: citation.source,
      page: citation.page,
      activeCitation: citation,
    });
  }, []);

  const goToPage = useCallback((page: number) => {
    setState((prev) => ({ ...prev, page }));
  }, []);

  const close = useCallback(() => {
    setState({ open: false, filename: null, page: 1, activeCitation: null });
  }, []);

  return { ...state, openCitation, goToPage, close };
}
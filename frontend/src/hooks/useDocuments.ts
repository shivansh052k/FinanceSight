import { useState, useCallback, useEffect } from "react";
import { fetchDocuments, ingestFiles } from "../api/client";
import type { Document } from "../types";

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchDocuments();
      setDocuments(data.documents);
      setTotalChunks(data.total_chunks);
    } catch {
      setError("Failed to fetch documents.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const upload = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      setUploading(true);
      setError(null);
      try {
        await ingestFiles(files);
        // poll until all accepted files reach complete/error
        const pollRef = { id: 0 };
        pollRef.id = window.setInterval(async () => {
        const data = await fetchDocuments();
        setDocuments(data.documents);
        setTotalChunks(data.total_chunks);
        const stillProcessing = data.documents.some((d) => d.status === "processing");
        if (!stillProcessing) {
            clearInterval(pollRef.id);
            setUploading(false);
        }
        }, 3000);
      } catch {
        setError("Upload failed. Please try again.");
        setUploading(false);
      }
    },
    []
  );

  return { documents, totalChunks, uploading, error, upload, refresh };
}
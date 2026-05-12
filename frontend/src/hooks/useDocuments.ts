import { useState, useCallback, useEffect } from "react";
import { fetchDocuments, ingestFiles, deleteDocument } from "../api/client";
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

  useEffect(() => { refresh(); }, [refresh]);

  const upload = useCallback((files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    ingestFiles(files).then(() => {
      const pollRef = { id: 0 };
      pollRef.id = window.setInterval(async () => {
        const data = await fetchDocuments();
        setDocuments(data.documents);
        setTotalChunks(data.total_chunks);
        if (!data.documents.some((d) => d.status === "processing")) {
          clearInterval(pollRef.id);
          setUploading(false);
        }
      }, 3000);
    }).catch(() => {
      setError("Upload failed.");
      setUploading(false);
    });
  }, []);

  const remove = useCallback(async (filename: string) => {
    try {
      await deleteDocument(filename);
      await refresh();
    } catch {
      setError(`Failed to remove ${filename}.`);
    }
  }, [refresh]);

  return { documents, totalChunks, uploading, error, upload, refresh, remove };
}
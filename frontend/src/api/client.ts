import axios from "axios";
import type {
  QueryRequest,
  QueryResponse,
  DocumentsResponse,
  IngestResponse,
} from "../types";

const api = axios.create({
  baseURL: "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

export async function queryDocuments(
  payload: QueryRequest
): Promise<QueryResponse> {
  const { data } = await api.post<QueryResponse>("/query", payload);
  return data;
}

export async function fetchDocuments(): Promise<DocumentsResponse> {
  const { data } = await api.get<DocumentsResponse>("/documents");
  return data;
}

export async function ingestFiles(files: File[]): Promise<IngestResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const { data } = await api.post<IngestResponse>("/ingest", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await api.get("/health");
    return true;
  } catch {
    return false;
  }
}
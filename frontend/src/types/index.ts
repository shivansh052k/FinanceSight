export interface Citation {
  id: number;
  source: string;
  page: number;
  text: string;
  bbox: number[];
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  intent?: string;
  confidence?: number;
  disclaimer?: string | null;
  insufficient_evidence?: boolean;
}

export interface QueryRequest {
  query: string;
  conversation_history?: { role: string; content: string }[];
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  intent: string;
  confidence: number;
  disclaimer: string | null;
  insufficient_evidence: boolean;
}

export interface Document {
  filename: string;
  status: "complete" | "processing" | "error";
}

export interface DocumentsResponse {
  documents: Document[];
  total_chunks: number;
}

export interface IngestFileResult {
  filename: string;
  status: "accepted" | "skipped" | "rejected";
  reason?: string;
}

export interface IngestResponse {
  files: IngestFileResult[];
}
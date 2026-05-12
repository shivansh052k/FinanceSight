import logging
import re
import threading
from dotenv import load_dotenv

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from app import guardrails
from app.embeddings import embed_query, embed_texts
from app.generator import generate
from app.hallucination import filter_hallucinations
from app.ingestion import ingest_pdf
from app.query_processor import process_query
from app.retrieval import build_bm25_index, retrieve
from app.vector_store import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PDFS_DIR = Path(__file__).parent.parent / "pdfs"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
_PDF_MAGIC = b"%PDF"

_status_lock = threading.Lock()
_ingest_semaphore = threading.Semaphore(1)
_ingestion_status: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    conversation_history: Optional[List[Dict[str, str]]] = None


class CitationResponse(BaseModel):
    id: int
    source: str
    page: int
    text: str
    bbox: List[float]


class QueryResponse(BaseModel):
    answer: str
    citations: List[CitationResponse]
    intent: str
    confidence: float
    disclaimer: Optional[str]
    insufficient_evidence: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_status(filename: str, status: str) -> None:
    with _status_lock:
        _ingestion_status[filename] = status


def _get_all_statuses() -> Dict[str, str]:
    with _status_lock:
        return dict(_ingestion_status)


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r'[/\\:\x00]', '_', name)
    if len(name) > 255:
        suffix = Path(name).suffix
        name = Path(name).stem[:255 - len(suffix)] + suffix
    return name or "unnamed.pdf"


def _validate_pdf(file: UploadFile, content: bytes) -> Optional[str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".pdf":
        return f"Only PDF files accepted (got '{suffix or 'no extension'}')"
    if content[:4] != _PDF_MAGIC:
        return "File does not appear to be a valid PDF (bad magic bytes)"
    if len(content) > MAX_FILE_SIZE:
        size_mb = len(content) / (1024 * 1024)
        return f"File exceeds 50 MB limit ({size_mb:.1f} MB)"
    return None


def _ingest_file(pdf_path: Path, source_name: str) -> None:
    with _ingest_semaphore:
        try:
            chunks = ingest_pdf(str(pdf_path))
            if not chunks:
                logger.warning("No chunks extracted from %s.", source_name)
                _set_status(source_name, "error")
                return
            embeddings = embed_texts([c["text"] for c in chunks])
            store.add(chunks, embeddings)
            store.save()
            build_bm25_index()
            _set_status(source_name, "complete")
            logger.info("Ingested %s: %d chunks.", source_name, len(chunks))
        except Exception as exc:
            logger.error("Ingestion failed for %s: %s", source_name, exc)
            _set_status(source_name, "error")


# ---------------------------------------------------------------------------
# App + lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    store.load()
    if store.chunk_count() > 0:
        build_bm25_index()
        logger.info(
            "Vector store loaded: %d chunks across %d source(s).",
            store.chunk_count(),
            len(store.get_sources()),
        )
    yield


app = FastAPI(
    title="FinanceSight RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "chunk_count": store.chunk_count(),
        "document_count": len(store.get_sources()),
    }


@app.get("/documents")
async def list_documents() -> Dict[str, Any]:
    ingested = set(store.get_sources())
    all_statuses = _get_all_statuses()
    documents: List[Dict[str, str]] = []

    for source in store.get_sources():
        documents.append({"filename": source, "status": "complete"})

    for filename, status in all_statuses.items():
        if filename not in ingested:
            documents.append({"filename": filename, "status": status})

    return {"documents": documents, "total_chunks": store.chunk_count()}

@app.delete("/documents/{filename}")
async def delete_document(filename: str) -> Dict[str, Any]:
    safe_name = _sanitize_filename(filename)
    if not store.has_source(safe_name):
        raise HTTPException(status_code=404, detail="Document not found")
    store.remove_source(safe_name)
    store.save()
    build_bm25_index()
    pdf_path = PDFS_DIR / safe_name
    if pdf_path.exists():
        pdf_path.unlink()
    with _status_lock:
        _ingestion_status.pop(safe_name, None)
    return {"filename": safe_name, "status": "removed"}

@app.post("/ingest", status_code=202)
async def ingest(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    results = []
    for file in files:
        content = await file.read()
        error = _validate_pdf(file, content)
        if error:
            results.append({"filename": file.filename, "status": "rejected", "reason": error})
            continue

        safe_name = _sanitize_filename(file.filename or "unknown.pdf")

        if store.has_source(safe_name) or _get_all_statuses().get(safe_name) == "processing":
            results.append({
                "filename": safe_name,
                "status": "skipped",
                "reason": "already ingested or processing",
            })
            continue

        dest = PDFS_DIR / safe_name
        dest.write_bytes(content)
        _set_status(safe_name, "processing")
        background_tasks.add_task(_ingest_file, dest, safe_name)
        results.append({"filename": safe_name, "status": "accepted"})

    return {"files": results}


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    guard = guardrails.check(request.query)
    if not guard["allowed"]:
        return QueryResponse(
            answer=guard["refusal_message"] or "Request refused.",
            citations=[],
            intent="refused",
            confidence=0.0,
            disclaimer=None,
            insufficient_evidence=False,
        )

    disclaimer = guard["disclaimer"]

    try:
        processed = process_query(request.query, request.conversation_history)
    except Exception as exc:
        logger.error("Query processing failed: %s", exc)
        return QueryResponse(
            answer="Failed to process your query. Please try again.",
            citations=[],
            intent="error",
            confidence=0.0,
            disclaimer=disclaimer,
            insufficient_evidence=False,
        )

    intent = processed["intent"]
    transformed = processed["transformed_query"]

    if intent == "conversational":
        result = generate(
            chunks=[],
            best_score=0.0,
            query=request.query,
            intent=intent,
            conversation_history=request.conversation_history,
            disclaimer=disclaimer,
        )
        return QueryResponse(**result)

    try:
        query_embedding = embed_query(transformed)
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        return QueryResponse(
            answer="Failed to embed your query. Please try again.",
            citations=[],
            intent=intent,
            confidence=0.0,
            disclaimer=disclaimer,
            insufficient_evidence=False,
        )

    retrieval_result = retrieve(query_embedding, transformed)
    chunks = retrieval_result["chunks"]
    best_score = retrieval_result["best_score"]

    result = generate(
        chunks=chunks,
        best_score=best_score,
        query=request.query,
        intent=intent,
        conversation_history=request.conversation_history,
        disclaimer=disclaimer,
    )

    if not result["insufficient_evidence"] and chunks:
        result["answer"] = filter_hallucinations(result["answer"], chunks)

    return QueryResponse(**result)


@app.get("/pdfs/{filename}")
async def serve_pdf(filename: str) -> FileResponse:
    safe_name = _sanitize_filename(filename)
    pdf_path = PDFS_DIR / safe_name
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    try:
        pdf_path.resolve().relative_to(PDFS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(str(pdf_path), media_type="application/pdf")
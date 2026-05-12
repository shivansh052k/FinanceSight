import logging
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4096
CHUNK_OVERLAP = 400

# Split priority: prefer semantic boundaries before hard cuts
_SPLIT_DELIMITERS: List[Tuple[str, int]] = [
    ("\n\n", 2),   # paragraph break — advance past both newlines
    (".\n", 2),    # sentence at line end
    (". ", 2),     # inline sentence boundary
    (" ",  1),     # word boundary
]


class Chunk(TypedDict):
    chunk_id: str
    text: str
    source: str
    page: int
    bbox: List[float]
    char_offset: int  # cumulative char offset within PDF across all blocks


class _RawBlock(TypedDict):
    text: str
    page: int
    bbox: List[float]
    source: str
    block_offset: int  # cumulative char offset of this block's start


def _find_split_boundary(text: str, start: int, end: int) -> int:
    """
    Search [start, end) for best split point using delimiter priority.
    Returns index after the delimiter so next chunk starts clean.
    Falls back to hard cut at end if no boundary found.
    """
    for delimiter, advance in _SPLIT_DELIMITERS:
        idx = text.rfind(delimiter, start, end)
        if idx != -1:
            return idx + advance
    return end


def _chunk_text(text: str) -> List[Tuple[str, int]]:
    """
    Split text into (chunk_text, start_offset_within_text) pairs.
    Guarantees forward progress — cursor always advances by at least 1 char.
    """
    chunks: List[Tuple[str, int]] = []
    cursor = 0
    length = len(text)

    while cursor < length:
        end = min(cursor + CHUNK_SIZE, length)

        if end < length:
            split_at = _find_split_boundary(text, cursor, end)
            if split_at <= cursor:
                split_at = end
        else:
            split_at = end

        chunk = text[cursor:split_at]
        if chunk.strip():
            chunks.append((chunk, cursor))

        # step back by overlap, but never behind cursor+1
        if split_at >= length:
            break
        next_cursor = split_at - CHUNK_OVERLAP
        cursor = max(next_cursor, cursor + 1)
        

    return chunks


def _extract_blocks(doc: fitz.Document, source: str) -> List[_RawBlock]:
    """
    Walk every page and collect text blocks with metadata.
    Image-only pages produce no blocks — logged as warning, not error.
    """
    blocks: List[_RawBlock] = []
    cumulative_offset = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        raw_blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,block_type)

        text_blocks = [b for b in raw_blocks if b[6] == 0]  # type 0 = text, 1 = image

        if not text_blocks:
            logger.debug(
                "Page %d of '%s' has no text blocks (image-only?); skipping.",
                page_num + 1, source
            )

        for b in text_blocks:
            text = b[4]
            if not text.strip():
                continue
            blocks.append(_RawBlock(
                text=text,
                page=page_num + 1,
                bbox=[b[0], b[1], b[2], b[3]],
                source=source,
                block_offset=cumulative_offset,
            ))
            cumulative_offset += len(text)

    logger.debug("Extracted %d text blocks from '%s'.", len(blocks), source)
    
    if not blocks:
        logger.warning("'%s': no text extracted from any page — may be scanned/image PDF.", source)
    return blocks


def ingest_pdf(pdf_path: str) -> List[Chunk]:
    """Parse a PDF and return production-ready chunks with source metadata."""
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {path.suffix!r}")

    doc: Optional[fitz.Document] = None
    try:
        try:
            doc = fitz.open(str(path))
        except fitz.FileDataError as exc:
            raise IOError(f"Corrupt or unreadable PDF '{pdf_path}': {exc}") from exc

        if doc.is_encrypted:
            raise PermissionError(f"PDF is encrypted and cannot be read: {pdf_path}")

        page_count = len(doc)
        if page_count == 0:
            raise ValueError(f"PDF has zero pages: {pdf_path}")

        source = path.name
        logger.info("Opened '%s' — %d page(s).", source, page_count)

        raw_blocks = _extract_blocks(doc, source)
        logger.info("'%s': %d blocks ready for chunking.", source, len(raw_blocks))

        chunks: List[Chunk] = []
        for block in raw_blocks:
            for chunk_text, local_offset in _chunk_text(block["text"]):
                abs_offset = block["block_offset"] + local_offset
                chunk_id = f"{source}::p{block['page']}::o{abs_offset}"
                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    source=source,
                    page=block["page"],
                    bbox=block["bbox"],
                    char_offset=abs_offset,
                ))

        logger.info("'%s': produced %d chunks.", source, len(chunks))
        return chunks

    finally:
        if doc is not None:
            doc.close()  # always release file handle, even on exception
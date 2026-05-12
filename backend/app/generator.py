import logging
import os
import re
from typing import Dict, List, Optional, TypedDict

from mistralai.client.sdk import Mistral

from app.ingestion import Chunk

logger = logging.getLogger(__name__)

GENERATION_MODEL = "mistral-large-latest"
SIMILARITY_THRESHOLD = 0.35   # below this → insufficient evidence, no LLM call
MAX_HISTORY_TURNS = 6         # cap conversation history injected into prompt

_INTENT_INSTRUCTIONS: Dict[str, str] = {
    "factual":       "Answer in 1-3 concise sentences with exact figures and units. Cite every claim with [N] markers.",
    "list":          "Answer as a markdown bulleted list. Every item must be specific, drawn from context, and cited with [N].",
    "table":         "Answer as a markdown table with clear column headers and exact figures. Cite the source of each row.",
    "comparison":    "Directly compare the entities or time periods using specific figures. Structure clearly. Cite every data point.",
    "conversational": "Respond naturally and concisely. No financial context is provided for this query.",
}

_MAX_TOKENS: Dict[str, int] = {
    "factual": 512,
    "list": 768,
    "table": 1024,
    "comparison": 1024,
    "conversational": 256,
}

_TEMPERATURE: Dict[str, float] = {
    "factual": 0.1,
    "list": 0.1,
    "table": 0.1,
    "comparison": 0.2,
    "conversational": 0.7,
}

_BASE_SYSTEM_PROMPT = """\
You are a precise financial analyst assistant specializing in SEC 10-K annual filings.

Rules:
- Answer using ONLY the numbered context blocks provided below. Do not use outside knowledge.
- Cite every factual claim with inline markers [1], [2], etc. corresponding to the context blocks.
- If the context lacks sufficient information to answer accurately, state that explicitly.
- Never fabricate figures, dates, names, or percentages.
- Do not speculate beyond what the context directly supports.

Context:
{context_blocks}

Answer format: {intent_instruction}"""

_CONVERSATIONAL_SYSTEM_PROMPT = """\
You are a helpful financial analyst assistant specializing in SEC 10-K annual filings.
Respond to conversational messages naturally and concisely.
If the user asks about specific financial data, let them know they can ask detailed questions about the ingested company filings."""

_INSUFFICIENT_EVIDENCE_ANSWER = (
    "I could not find sufficient evidence in the available financial filings to answer this question. "
    "Try rephrasing your query or ensure the relevant filing has been ingested."
)


class CitationInfo(TypedDict):
    id: int
    source: str
    page: int
    text: str    # excerpt from chunk
    bbox: List[float]


class GenerationResult(TypedDict):
    answer: str
    citations: List[CitationInfo]
    intent: str
    confidence: float
    disclaimer: Optional[str]
    insufficient_evidence: bool


def _get_client() -> Mistral:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY not set in environment")
    return Mistral(api_key=api_key)


def _excerpt(text: str, max_len: int = 300) -> str:
    """Truncate text at word boundary to avoid mid-word cuts in citation previews."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rfind(" ")
    return (text[:cut] + "…") if cut > 0 else (text[:max_len] + "…")


def _build_context_blocks(chunks: List[Chunk]) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{i}] Source: {chunk['source']} | Page {chunk['page']}\n"
            f'"{chunk["text"]}"'
        )
    return "\n\n".join(blocks)


def _extract_citations(answer: str, chunks: List[Chunk]) -> List[CitationInfo]:
    """Parse [N] markers from answer and map to source chunks. Invalid refs silently ignored."""
    raw_refs = set(int(m) for m in re.findall(r"\[(\d+)\]", answer))
    citations: List[CitationInfo] = []
    for ref in sorted(raw_refs):
        idx = ref - 1  # 1-based in prompt → 0-based index
        if 0 <= idx < len(chunks):
            chunk = chunks[idx]
            citations.append(CitationInfo(
                id=ref,
                source=chunk["source"],
                page=chunk["page"],
                text=_excerpt(chunk["text"]),
                bbox=chunk["bbox"],
            ))
        else:
            logger.warning("LLM cited [%d] but only %d chunks provided — ignoring.", ref, len(chunks))
    return citations


def _trim_history(
    conversation_history: Optional[List[Dict[str, str]]],
) -> List[Dict[str, str]]:
    if not conversation_history:
        return []
    max_messages = MAX_HISTORY_TURNS * 2  # user + assistant per turn
    return list(conversation_history[-max_messages:])


def generate(
    chunks: List[Chunk],
    best_score: float,
    query: str,
    intent: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    disclaimer: Optional[str] = None,
) -> GenerationResult:
    """
    Generate a grounded, cited answer from retrieved chunks.

    Returns insufficient_evidence=True (no LLM call) when:
    - intent is not conversational AND chunks are empty
    - intent is not conversational AND best_score < SIMILARITY_THRESHOLD
    """
    # --- Conversational: bypass retrieval entirely ---
    if intent == "conversational":
        return _generate_conversational(query, conversation_history, disclaimer)

    # --- Threshold check: insufficient evidence ---
    if not chunks or best_score < SIMILARITY_THRESHOLD:
        logger.info(
            "Insufficient evidence: chunks=%d, best_score=%.3f, threshold=%.2f.",
            len(chunks), best_score, SIMILARITY_THRESHOLD,
        )
        return GenerationResult(
            answer=_INSUFFICIENT_EVIDENCE_ANSWER,
            citations=[],
            intent=intent,
            confidence=best_score,
            disclaimer=disclaimer,
            insufficient_evidence=True,
        )

    # --- Build prompt ---
    context_blocks = _build_context_blocks(chunks)
    intent_instruction = _INTENT_INSTRUCTIONS.get(intent, _INTENT_INSTRUCTIONS["factual"])
    system_prompt = _BASE_SYSTEM_PROMPT.format(
        context_blocks=context_blocks,
        intent_instruction=intent_instruction,
    )

    history = _trim_history(conversation_history)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": query}]
    )

    try:
        client = _get_client()
        response = client.chat.complete(
            model=GENERATION_MODEL,
            messages=messages,
            temperature=_TEMPERATURE.get(intent, 0.1),
            max_tokens=_MAX_TOKENS.get(intent, 512),
        )
        answer = (response.choices[0].message.content or "").strip()

        if not answer:
            raise ValueError("Empty response from generation model")

        citations = _extract_citations(answer, chunks)
        logger.info(
            "Generated answer: intent=%r, citations=%d, confidence=%.3f.",
            intent, len(citations), best_score,
        )
        return GenerationResult(
            answer=answer,
            citations=citations,
            intent=intent,
            confidence=best_score,
            disclaimer=disclaimer,
            insufficient_evidence=False,
        )

    except Exception as exc:
        logger.error("Generation failed: %s", exc)
        return GenerationResult(
            answer="I encountered an error generating a response. Please try again.",
            citations=[],
            intent=intent,
            confidence=best_score,
            disclaimer=disclaimer,
            insufficient_evidence=False,
        )


def _generate_conversational(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]],
    disclaimer: Optional[str],
) -> GenerationResult:
    """Handle conversational intent — no context, no citations, no threshold check."""
    history = _trim_history(conversation_history)
    messages = (
        [{"role": "system", "content": _CONVERSATIONAL_SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": query}]
    )

    try:
        client = _get_client()
        response = client.chat.complete(
            model=GENERATION_MODEL,
            messages=messages,
            temperature=_TEMPERATURE["conversational"],
            max_tokens=_MAX_TOKENS["conversational"],
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = "I'm here to help with questions about financial filings. What would you like to know?"

        return GenerationResult(
            answer=answer,
            citations=[],
            intent="conversational",
            confidence=1.0,
            disclaimer=disclaimer,
            insufficient_evidence=False,
        )

    except Exception as exc:
        logger.error("Conversational generation failed: %s", exc)
        return GenerationResult(
            answer="I'm here to help. Please ask a question about the ingested financial filings.",
            citations=[],
            intent="conversational",
            confidence=1.0,
            disclaimer=disclaimer,
            insufficient_evidence=False,
        )
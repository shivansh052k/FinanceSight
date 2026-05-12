import json
import logging
import os
from typing import Dict, List, Optional, TypedDict

from mistralai.client.sdk import Mistral


logger = logging.getLogger(__name__)

INTENT_MODEL = "mistral-small-latest"
TRANSFORM_MODEL = "mistral-small-latest"
MAX_HISTORY_TURNS = 6  # cap conversation history to avoid token bloat

VALID_INTENTS = frozenset({"conversational", "factual", "list", "table", "comparison"})
DEFAULT_INTENT = "factual"

_INTENT_SYSTEM_PROMPT = """\
You are a query classifier for a financial document RAG system backed by SEC 10-K annual filings.

Classify the user query into exactly one intent:
- conversational: greetings, chitchat, or questions unrelated to financial filings
- factual: seeks one specific number, date, name, or single fact
- list: expects multiple items as a bulleted or numbered list
- table: expects data organized into rows and columns
- comparison: compares values across companies, segments, or time periods

Examples:
  "Hello, how are you?" → conversational
  "What was Apple's net income in fiscal 2023?" → factual
  "What risk factors did Meta highlight in their 2024 10-K?" → list
  "Show me Amazon's revenue breakdown by segment" → table
  "How did NVIDIA's gross margin change from 2023 to 2024?" → comparison
  "Compare operating expenses across Apple, Google, and Meta" → comparison

Respond with ONLY valid JSON: {"intent": "<intent>"}
No explanation. No markdown. No code block."""

_TRANSFORM_SYSTEM_PROMPT = """\
You are a financial search query optimizer for SEC 10-K annual filings.

Rewrite the query to maximize retrieval from dense financial documents:
- Spell out company names in full (Apple Inc., Microsoft Corporation, Alphabet Inc.)
- Expand abbreviations (R&D → research and development, EPS → earnings per share, CapEx → capital expenditures)
- Add SEC filing section names when relevant (Risk Factors, Management Discussion and Analysis, Liquidity and Capital Resources)
- For comparison queries, ensure all entities and time periods are stated explicitly
- For list queries, add phrasing like "list of" or "key factors" to surface enumerated content
- Keep output under 60 words
- Preserve the original meaning exactly

The query intent is: {intent}

Respond with ONLY the rewritten query. No explanation. No prefix."""


class ProcessedQuery(TypedDict):
    original_query: str
    transformed_query: str
    intent: str


def _get_client() -> Mistral:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY not set in environment")
    return Mistral(api_key=api_key)


def _parse_intent(raw: str) -> str:
    """Extract intent from LLM response. Returns DEFAULT_INTENT on any parse failure."""
    raw = raw.strip()
    # strip accidental markdown code fences
    if raw.startswith("```"):
        raw = raw.split("```")[1].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        data = json.loads(raw)
        intent = str(data.get("intent", "")).lower().strip()
        if intent in VALID_INTENTS:
            return intent
        logger.warning("Unknown intent %r from LLM — defaulting to %r.", intent, DEFAULT_INTENT)
        return DEFAULT_INTENT
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Intent parse failed (%s) on response %r — defaulting to %r.",
                       exc, raw[:100], DEFAULT_INTENT)
        return DEFAULT_INTENT


def _build_history_messages(
    conversation_history: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Trim history to last MAX_HISTORY_TURNS user+assistant pairs."""
    # each turn = 1 user + 1 assistant message = 2 entries
    max_messages = MAX_HISTORY_TURNS * 2
    return conversation_history[-max_messages:] if conversation_history else []


def detect_intent(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    client: Optional[Mistral] = None,
) -> str:
    """
    Classify query intent using mistral-small-latest.
    Falls back to DEFAULT_INTENT on any API or parse error.
    """
    client = client or _get_client()
    messages = _build_history_messages(conversation_history or [])
    messages.append({"role": "user", "content": query})

    try:
        response = client.chat.complete(
            model=INTENT_MODEL,
            messages=[{"role": "system", "content": _INTENT_SYSTEM_PROMPT}] + messages,
            temperature=0.0,
            max_tokens=32,
        )
        raw = response.choices[0].message.content or ""
        intent = _parse_intent(raw)
        logger.info("Intent detected: %r for query: %.60r", intent, query)
        return intent
    except Exception as exc:
        logger.error("Intent detection failed (%s) — defaulting to %r.", exc, DEFAULT_INTENT)
        return DEFAULT_INTENT


def transform_query(query: str, intent: str, client: Optional[Mistral] = None) -> str:
    """
    Rewrite query for better vector retrieval using mistral-small-latest.
    Returns original query on any API or empty-response error.
    Skipped for conversational intent — no retrieval needed.
    """
    if intent == "conversational":
        return query  # no retrieval — transformation pointless

    client = client or _get_client()
    prompt = _TRANSFORM_SYSTEM_PROMPT.format(intent=intent)

    try:
        response = client.chat.complete(
            model=TRANSFORM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.2,
            max_tokens=128,
        )
        transformed = (response.choices[0].message.content or "").strip()

        if not transformed:
            logger.warning("Empty transformed query — using original.")
            return query

        logger.info("Query transformed: %.80r → %.80r", query, transformed)
        return transformed
    except Exception as exc:
        logger.error("Query transformation failed (%s) — using original query.", exc)
        return query


def process_query(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> ProcessedQuery:
    """
    Full query processing pipeline: intent detection + query transformation.
    Raises ValueError for empty query. All API failures handled internally.
    """
    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    client = _get_client()  # single client for both calls
    intent = detect_intent(query, conversation_history, client)
    transformed = transform_query(query, intent, client)

    return ProcessedQuery(
        original_query=query,
        transformed_query=transformed,
        intent=intent,
    )
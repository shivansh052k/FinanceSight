import logging
import re
from typing import List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)

INVESTMENT_DISCLAIMER = (
    "Disclaimer: Nothing in this response constitutes investment advice, "
    "a recommendation to buy or sell any security, or a solicitation of any investment. "
    "Consult a licensed financial advisor before making investment decisions."
)

MEDICAL_DISCLAIMER = (
    "Note: This system provides information from SEC financial filings only "
    "and cannot provide medical advice. Consult a qualified healthcare professional "
    "for any health-related concerns."
)

_PII_REFUSAL = (
    "Your query contains personal information (such as an email address, phone number, "
    "SSN, or credit card number) that cannot be processed. "
    "Please remove any personal data and rephrase your question."
)
_INJECTION_REFUSAL = (
    "Your query contains patterns consistent with prompt injection. "
    "Please ask a genuine question about the financial documents."
)
_INVESTMENT_REFUSAL = (
    "This system cannot provide investment advice or recommendations to buy, sell, "
    "or hold any security. " + INVESTMENT_DISCLAIMER
)

_OUT_OF_SCOPE_REFUSAL = (
    "This system answers questions about financial data in SEC 10-K filings only. "
    "Questions about product health benefits, medical applications, or non-financial topics "
    "are outside the scope of this knowledge base."
)

# PII: (label, compiled pattern) — label used in logs, never log query content
_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "email",
        re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'),
    ),
    (
        "phone (NNN-NNN-NNNN)",
        re.compile(r'(?<!\d)\d{3}[.\-\s]\d{3}[.\-\s]\d{4}(?!\d)'),
    ),
    (
        "phone ((NNN) NNN-NNNN)",
        re.compile(r'(?<!\d)\(\d{3}\)\s*\d{3}[.\-\s]\d{4}(?!\d)'),
    ),
    (
        "phone (+1 NNN-NNN-NNNN)",
        re.compile(r'(?<!\d)\+?1[.\-\s]\d{3}[.\-\s]\d{3}[.\-\s]\d{4}(?!\d)'),
    ),
    (
        "SSN",
        re.compile(r'(?<!\d)\d{3}[-\s]\d{2}[-\s]\d{4}(?!\d)'),
    ),
    (
        "credit card",
        # Prefix-anchored: Visa (4), Mastercard (51-55), Amex (34/37), Discover (6011)
        # Require at least one separator to avoid false-positives on revenue figures
        re.compile(
            r'(?<!\d)'
            r'(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)'
            r'[\s\-]'
            r'\d{4}[\s\-]\d{4}[\s\-]\d{3,4}'
            r'(?!\d)'
        ),
    ),
]

_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r'ignore\s+(previous|all|above|prior)\s+(instructions?|rules?|context|prompt)', re.IGNORECASE),
    re.compile(r'\byou\s+are\s+now\s+(a|an)\b', re.IGNORECASE),
    re.compile(r'\bact\s+as\s+(a|an)\b', re.IGNORECASE),
    re.compile(r'\bpretend\s+(you\s+are|to\s+be)\b', re.IGNORECASE),
    re.compile(r'\bforget\s+(your|all|previous|prior)\s+(instructions?|rules?|context)\b', re.IGNORECASE),
    re.compile(r'\bnew\s+instructions?\s*:', re.IGNORECASE),
    re.compile(r'\bsystem\s+prompt\b', re.IGNORECASE),
    re.compile(r'\bjailbreak\b', re.IGNORECASE),
    re.compile(r'\boverride\s+(your|all)\s+(instructions?|rules?)\b', re.IGNORECASE),
    re.compile(r'\bdisregard\s+(previous|all|your)\b', re.IGNORECASE),
]

_INVESTMENT_PATTERNS: List[re.Pattern] = [
    re.compile(r'\bshould\s+i\s+(buy|sell|invest|short|hold|trade)\b', re.IGNORECASE),
    re.compile(r'\bwould\s+you\s+recommend\s+(buying|selling|investing|shorting|holding)\b', re.IGNORECASE),
    re.compile(r'\b(buy|sell|short|hold)\s+recommendation\b', re.IGNORECASE),
    re.compile(r'\bis\s+\w+\s+(a\s+)?(good|worthwhile?|safe)\s+(investment|buy|stock|trade)\b', re.IGNORECASE),
    re.compile(r'\b(recommend|advise|suggest)\s+(buying|selling|investing|shorting)\b', re.IGNORECASE),
    re.compile(r'\bprice\s+target\b', re.IGNORECASE),
    re.compile(
        r'\b(will|would)\s+\w+\s+(stock|share|price)\s+(go\s+up|rise|increase|fall|drop|decline)\b',
        re.IGNORECASE,
    ),
    re.compile(r'\bshould\s+i\s+invest\b', re.IGNORECASE),
    # re.compile(r'\bhealth\s+benefit', re.IGNORECASE),
]

_MEDICAL_PATTERNS: List[re.Pattern] = [
    re.compile(
        r'\b(diagnos(e|is|ed|ing)|symptom|treatment|medication|prescription'
        r'|drug\s+dosage|disease|illness|therapy|cure)\b',
        re.IGNORECASE,
    ),
    re.compile(r'\bmedical\s+advice\b', re.IGNORECASE),
    re.compile(r'\b(health\s+benefit|wellness|medical\s+use|clinical)\b', re.IGNORECASE),
]

_OUT_OF_SCOPE_PATTERNS: List[re.Pattern] = [
    re.compile(r'\bhealth\s+benefit', re.IGNORECASE),
    re.compile(r'\bphysical\s+benefit', re.IGNORECASE),
]


class GuardrailResult(TypedDict):
    allowed: bool
    refusal_message: Optional[str]  # non-None when allowed=False
    disclaimer: Optional[str]       # non-None when allowed=True but disclosure required


def check(query: str) -> GuardrailResult:
    """
    Run all guardrail checks in priority order. Returns on first refusal.

    Check order: empty → PII → prompt injection → investment advice → medical.
    Medical queries are allowed but flagged with a disclaimer — never refused.
    All other failures are hard refusals with no LLM call.
    """
    if not isinstance(query, str) or not query.strip():
        return GuardrailResult(
            allowed=False,
            refusal_message="Query cannot be empty.",
            disclaimer=None,
        )

    for label, pattern in _PII_PATTERNS:
        if pattern.search(query):
            logger.warning("Guardrails: PII detected (%s) — query refused.", label)
            return GuardrailResult(
                allowed=False,
                refusal_message=_PII_REFUSAL,
                disclaimer=None,
            )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            logger.warning("Guardrails: prompt injection pattern detected — query refused.")
            return GuardrailResult(
                allowed=False,
                refusal_message=_INJECTION_REFUSAL,
                disclaimer=None,
            )

    for pattern in _INVESTMENT_PATTERNS:
        if pattern.search(query):
            logger.warning("Guardrails: investment advice request detected — query refused.")
            return GuardrailResult(
                allowed=False,
                refusal_message=_INVESTMENT_REFUSAL,
                disclaimer=None,
            )

    for pattern in _MEDICAL_PATTERNS:
        if pattern.search(query):
            logger.info("Guardrails: medical-adjacent query — appending disclaimer, proceeding.")
            return GuardrailResult(
                allowed=True,
                refusal_message=None,
                disclaimer=MEDICAL_DISCLAIMER,
            )
    
    for pattern in _OUT_OF_SCOPE_PATTERNS:
        if pattern.search(query):
            logger.warning("Guardrails: out-of-scope query detected — refused.")
            return GuardrailResult(
                allowed=False,
                refusal_message=_OUT_OF_SCOPE_REFUSAL,
                disclaimer=None,
            )

    return GuardrailResult(allowed=True, refusal_message=None, disclaimer=None)
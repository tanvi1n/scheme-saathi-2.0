"""
skills/normalize.py — Occupation normalization layer.

Responsibility: translate raw user business descriptions (in any language)
into a single canonical occupation key from the closed vocabulary.

This module performs CLASSIFICATION ONLY.
It does not perform discovery, eligibility checking, or scheme lookup.
It never receives schemes.json, eligibility criteria, or scheme amounts.

Pipeline position:
    raw user text
        ↓
    normalize_occupation()      ← this module
        ↓
    canonical occupation key
        ↓
    get_candidate_schemes()     ← skills/discover.py
        ↓
    check_scheme_eligibility()  ← eligibility_engine.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────
# Closed canonical vocabulary — single source of truth
# ──────────────────────────────────────────────────────────────────────

CANONICAL_OCCUPATIONS: frozenset = frozenset({
    "tailor",
    "kirana",
    "salon",
    "vegetable_vendor",
    "mechanic",
    "carpenter",
    "auto_driver",
    "taxi_driver",
    "street_vendor",
    "dairy_business",
    "small_manufacturer",
})

# Human-readable display list shown to users when normalization fails
OCCUPATION_DISPLAY_LIST = (
    "tailor (టైలర్), kirana (కిరాణా), salon (సెలూన్), "
    "vegetable_vendor (కూరగాయల వ్యాపారి), mechanic (మెకానిక్), "
    "carpenter (వడ్రంగి), auto_driver (ఆటో డ్రైవర్), "
    "taxi_driver (టాక్సీ డ్రైవర్), street_vendor (వీధి వ్యాపారి), "
    "dairy_business (పాడి వ్యాపారం), small_manufacturer (చిన్న తయారీ)"
)

# ──────────────────────────────────────────────────────────────────────
# Deterministic keyword fallback (local — no import from discover.py
# to avoid circular dependency)
# ──────────────────────────────────────────────────────────────────────

_FALLBACK_KEYWORDS: dict = {
    "tailor": [
        "tailor", "tailoring", "tailors", "darzi", "darji", "silai",
        "clothing", "garment", "stitch", "stitching",
        "టైలర్", "టైలరింగ్", "కుట్టు",
    ],
    "kirana": [
        "kirana", "grocery", "general store", "retail", "shop",
        "కిరాణా", "కిరాణ", "దుకాణం", "గ్రోసరీ",
    ],
    "salon": [
        "salon", "saloon", "barber", "beauty", "hair", "parlour", "parlor",
        "సెలూన్", "సలూన్", "క్షౌరం", "బ్యూటీ",
    ],
    "vegetable_vendor": [
        "vegetable", "sabzi", "sabji", "fruit", "produce",
        "కూరగాయలు", "కూరగాయ", "పండ్లు",
    ],
    "mechanic": [
        "mechanic", "repair", "garage", "workshop", "service center",
        "మెకానిక్", "మరమ్మత్తు",
    ],
    "carpenter": [
        "carpenter", "wood", "furniture", "woodwork", "carpenter",
        "వడ్రంగి", "చెక్క", "ఫర్నిచర్",
    ],
    "auto_driver": [
        "auto", "auto-rickshaw", "autorickshaw", "rickshaw", "three-wheeler",
        "ఆటో", "రిక్షా", "ఆటో రిక్షా",
    ],
    "taxi_driver": [
        "taxi", "cab", "ola", "uber", "car driver", "cab driver",
        "టాక్సీ", "క్యాబ్",
    ],
    "street_vendor": [
        "street vendor", "hawker", "mobile cart", "thela", "rehri", "footpath",
        "వీధి వ్యాపారి", "వీధి", "చిరు వ్యాపారి",
    ],
    "dairy_business": [
        "dairy", "milk", "cattle", "cow", "buffalo", "animal husbandry",
        "పాడి", "పాల వ్యాపారం", "ఆవు", "గేదె", "పశుపోషణ",
    ],
    "small_manufacturer": [
        "manufacturer", "manufacturing", "production", "factory", "unit",
        "తయారీ", "ఉత్పత్తి", "పరిశ్రమ",
    ],
}


def _fallback_normalize(raw_text: str) -> Optional[str]:
    """
    Deterministic keyword scan of raw_text.
    Returns a canonical occupation key or None.
    Called when the LLM is unavailable.
    """
    text = raw_text.lower()
    for occupation, keywords in _FALLBACK_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return occupation
    return None


# ──────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────

@dataclass
class OccupationResult:
    """
    Result of normalize_occupation().

    canonical:      one of CANONICAL_OCCUPATIONS, or None if not recognised
    raw_llm_output: what the LLM actually returned (empty string if LLM not called)
    source:         "llm"       — LLM was called and returned a valid vocabulary word
                    "llm"       — LLM was called but returned out-of-vocabulary (canonical=None)
                    "fallback"  — LLM failed; deterministic keyword fallback was used
                    "error"     — input was blank or None; neither path attempted
    """
    canonical: Optional[str]
    raw_llm_output: str
    source: str  # "llm" | "fallback" | "error"


# ──────────────────────────────────────────────────────────────────────
# LLM prompt
# ──────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a business-type classifier. "
    "The user will describe their work in any language "
    "(Telugu, Hindi, English, Hinglish, or mixed). "
    "Output EXACTLY ONE word from this list, nothing else:\n"
    "tailor, kirana, salon, vegetable_vendor, mechanic, carpenter, "
    "auto_driver, taxi_driver, street_vendor, dairy_business, small_manufacturer\n"
    "If the description does not match any of these, output: unknown"
)


def _call_groq(raw_text: str, groq_client) -> str:
    """
    Call the Groq API (or injected mock client) and return the raw response.
    Raises any exception to the caller — does not catch here.

    groq_client interface (duck-typed):
        groq_client.complete(prompt: str) -> str

    When groq_client is None, uses the real Groq API directly.
    """
    if groq_client is not None:
        # Injected test double — must implement .complete(prompt) -> str
        return groq_client.complete(raw_text)

    # Real Groq API call — same pattern as agent.py's ask_llm()
    api_key = os.getenv("GROQ_API_KEY")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            "temperature": 0,
            "max_tokens": 10,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def normalize_occupation(raw_text: str, groq_client=None) -> OccupationResult:
    """
    Translate a raw user business description into a canonical occupation key.

    Args:
        raw_text:    The user's description in any language.
        groq_client: Optional injectable mock for testing.
                     Must implement .complete(prompt: str) -> str.
                     When None, uses the real Groq API.

    Returns:
        OccupationResult with:
            canonical  — a key from CANONICAL_OCCUPATIONS, or None
            raw_llm_output — what the LLM returned (or "" if not called)
            source     — "llm", "fallback", or "error"

    Never raises. All errors produce a valid OccupationResult.
    """
    # ── Guard: blank input ────────────────────────────────────────────
    if not raw_text or not raw_text.strip():
        return OccupationResult(canonical=None, raw_llm_output="", source="error")

    # ── Strategy 1: LLM classification ───────────────────────────────
    try:
        raw_output = _call_groq(raw_text, groq_client)
        # Normalise: strip whitespace, lowercase
        normalised = raw_output.strip().lower()
        # Accept only if the entire output is a single canonical key.
        # "tailor shop owner" would not match — whole string must be the key.
        if normalised in CANONICAL_OCCUPATIONS:
            return OccupationResult(
                canonical=normalised,
                raw_llm_output=raw_output,
                source="llm",
            )
        # Out-of-vocabulary (including "unknown") → canonical=None
        return OccupationResult(
            canonical=None,
            raw_llm_output=raw_output,
            source="llm",
        )

    except Exception:
        # ── Strategy 2: deterministic keyword fallback ────────────────
        canonical = _fallback_normalize(raw_text)
        return OccupationResult(
            canonical=canonical,
            raw_llm_output="",
            source="fallback",
        )

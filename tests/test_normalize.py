"""
tests/test_normalize.py — Unit tests for skills/normalize.py

Key invariants tested:
- normalize_occupation() never raises
- Valid canonical LLM output → OccupationResult.canonical set correctly
- Out-of-vocabulary or "unknown" LLM output → canonical=None, source="llm"
- LLM exception → deterministic fallback, source="fallback"
- Blank input → canonical=None, source="error"
- Case normalization of LLM output
- Extra text in LLM output is rejected (whole-string match required)
- Telugu and Hinglish inputs handled by fallback
- CANONICAL_OCCUPATIONS is a frozenset of exactly the 11 expected keys

All tests use injected mock clients. No real Groq API calls are made.
"""

import pytest
from skills.normalize import (
    normalize_occupation,
    OccupationResult,
    CANONICAL_OCCUPATIONS,
    OCCUPATION_DISPLAY_LIST,
)


# ──────────────────────────────────────────────────────────────────────
# Mock clients
# ──────────────────────────────────────────────────────────────────────

class MockClient:
    """Returns a fixed string from .complete()."""
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


class ErrorClient:
    """Always raises an exception from .complete()."""
    def __init__(self, exc=None):
        self._exc = exc or ConnectionError("simulated timeout")

    def complete(self, prompt: str) -> str:
        raise self._exc


# ──────────────────────────────────────────────────────────────────────
# 1. Exact canonical English input → tailor
# ──────────────────────────────────────────────────────────────────────

def test_exact_canonical_tailor():
    """LLM returns 'tailor' → canonical='tailor', source='llm'."""
    result = normalize_occupation("tailor", MockClient("tailor"))
    assert result.canonical == "tailor"
    assert result.source == "llm"
    assert result.raw_llm_output == "tailor"


# ──────────────────────────────────────────────────────────────────────
# 2. Hinglish input → tailor (LLM classifies it)
# ──────────────────────────────────────────────────────────────────────

def test_hinglish_input_tailor():
    """LLM receives 'darzi ka kaam karta hoon' and returns 'tailor'."""
    result = normalize_occupation("darzi ka kaam karta hoon", MockClient("tailor"))
    assert result.canonical == "tailor"
    assert result.source == "llm"


# ──────────────────────────────────────────────────────────────────────
# 3. Telugu input → tailor (LLM classifies it)
# ──────────────────────────────────────────────────────────────────────

def test_telugu_input_tailor():
    """LLM receives Telugu tailor description and returns 'tailor'."""
    result = normalize_occupation("నేను టైలరింగ్ చేస్తున్నాను", MockClient("tailor"))
    assert result.canonical == "tailor"
    assert result.source == "llm"


# ──────────────────────────────────────────────────────────────────────
# 4. Valid LLM outputs for all canonical occupations
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("occupation", sorted(CANONICAL_OCCUPATIONS))
def test_all_canonical_occupations_accepted(occupation):
    """Every key in CANONICAL_OCCUPATIONS must be accepted as valid LLM output."""
    result = normalize_occupation("some business", MockClient(occupation))
    assert result.canonical == occupation, (
        f"Expected canonical='{occupation}', got '{result.canonical}'"
    )
    assert result.source == "llm"


# ──────────────────────────────────────────────────────────────────────
# 5. Invalid (out-of-vocabulary) LLM output → None
# ──────────────────────────────────────────────────────────────────────

def test_invalid_llm_output_returns_none():
    """LLM returning an unrecognised word → canonical=None, source='llm'."""
    result = normalize_occupation("underwater welder", MockClient("diver"))
    assert result.canonical is None
    assert result.source == "llm"
    assert result.raw_llm_output == "diver"


# ──────────────────────────────────────────────────────────────────────
# 6. LLM returns "unknown" → canonical=None
# ──────────────────────────────────────────────────────────────────────

def test_llm_unknown_returns_none():
    """'unknown' is not in CANONICAL_OCCUPATIONS → canonical=None."""
    result = normalize_occupation("chartered accountant", MockClient("unknown"))
    assert result.canonical is None
    assert result.source == "llm"


# ──────────────────────────────────────────────────────────────────────
# 7. LLM exception → fallback activates
# ──────────────────────────────────────────────────────────────────────

def test_llm_exception_triggers_fallback():
    """Connection error → fallback used, source='fallback'."""
    result = normalize_occupation("tailor shop", ErrorClient())
    assert result.source == "fallback"
    # fallback keyword scan should recognise "tailor"
    assert result.canonical == "tailor"


def test_llm_exception_unknown_occupation_fallback():
    """Connection error on completely unknown input → canonical=None, source='fallback'."""
    result = normalize_occupation("underwater welding contracts", ErrorClient())
    assert result.source == "fallback"
    assert result.canonical is None


# ──────────────────────────────────────────────────────────────────────
# 8. Blank input → error, no API call attempted
# ──────────────────────────────────────────────────────────────────────

def test_blank_input_returns_error():
    """Blank string → canonical=None, source='error', no LLM call."""
    result = normalize_occupation("", MockClient("tailor"))
    assert result.canonical is None
    assert result.source == "error"


def test_whitespace_only_input_returns_error():
    """Whitespace-only input → source='error'."""
    result = normalize_occupation("   ", MockClient("tailor"))
    assert result.canonical is None
    assert result.source == "error"


def test_none_equivalent_empty_returns_error():
    """None-like empty string edge case."""
    result = normalize_occupation("", MockClient("kirana"))
    assert result.source == "error"


# ──────────────────────────────────────────────────────────────────────
# 9. Uppercase / mixed-case LLM output is normalised
# ──────────────────────────────────────────────────────────────────────

def test_uppercase_llm_output_normalised():
    """'TAILOR' from LLM should be lowercased and accepted."""
    result = normalize_occupation("stitching work", MockClient("TAILOR"))
    assert result.canonical == "tailor"
    assert result.source == "llm"


def test_mixedcase_llm_output_normalised():
    """'Auto_Driver' should be lowercased and accepted."""
    result = normalize_occupation("auto chalata hoon", MockClient("Auto_Driver"))
    assert result.canonical == "auto_driver"
    assert result.source == "llm"


def test_leading_trailing_whitespace_in_llm_output():
    """LLM output with surrounding whitespace is stripped and accepted."""
    result = normalize_occupation("kirana shop owner", MockClient("  kirana  "))
    assert result.canonical == "kirana"
    assert result.source == "llm"


# ──────────────────────────────────────────────────────────────────────
# 10. Extra text in LLM output is rejected (whole-string match)
# ──────────────────────────────────────────────────────────────────────

def test_extra_text_in_llm_output_rejected():
    """
    'tailor shop owner' contains 'tailor' but is not the canonical key itself.
    The whole normalised string must match — substring is not enough.
    """
    result = normalize_occupation("I run a stitching shop", MockClient("tailor shop owner"))
    assert result.canonical is None
    assert result.source == "llm"


def test_sentence_in_llm_output_rejected():
    """LLM returning a sentence instead of one word → rejected."""
    result = normalize_occupation("salon business", MockClient("This person runs a salon"))
    assert result.canonical is None
    assert result.source == "llm"


# ──────────────────────────────────────────────────────────────────────
# Fallback keyword coverage — extra cases
# ──────────────────────────────────────────────────────────────────────

def test_fallback_telugu_auto():
    """Telugu 'ఆటో' should map to auto_driver via fallback."""
    result = normalize_occupation("ఆటో నడుపుతున్నాను", ErrorClient())
    assert result.source == "fallback"
    assert result.canonical == "auto_driver"


def test_fallback_hindi_dairy():
    """Hindi 'dairy' keyword should map to dairy_business via fallback."""
    result = normalize_occupation("main dairy chalata hoon", ErrorClient())
    assert result.source == "fallback"
    assert result.canonical == "dairy_business"


def test_fallback_kirana():
    """Keyword 'kirana' in text should resolve via fallback."""
    result = normalize_occupation("kirana dukan hai mera", ErrorClient())
    assert result.source == "fallback"
    assert result.canonical == "kirana"


# ──────────────────────────────────────────────────────────────────────
# OccupationResult shape
# ──────────────────────────────────────────────────────────────────────

def test_result_is_occupation_result_instance():
    result = normalize_occupation("tailor", MockClient("tailor"))
    assert isinstance(result, OccupationResult)


def test_result_has_required_fields():
    result = normalize_occupation("tailor", MockClient("tailor"))
    assert hasattr(result, "canonical")
    assert hasattr(result, "raw_llm_output")
    assert hasattr(result, "source")


# ──────────────────────────────────────────────────────────────────────
# CANONICAL_OCCUPATIONS vocabulary
# ──────────────────────────────────────────────────────────────────────

def test_canonical_occupations_is_frozenset():
    assert isinstance(CANONICAL_OCCUPATIONS, frozenset)


def test_canonical_occupations_has_11_entries():
    assert len(CANONICAL_OCCUPATIONS) == 11


def test_canonical_occupations_contains_expected_keys():
    expected = {
        "tailor", "kirana", "salon", "vegetable_vendor", "mechanic",
        "carpenter", "auto_driver", "taxi_driver", "street_vendor",
        "dairy_business", "small_manufacturer",
    }
    assert CANONICAL_OCCUPATIONS == expected


# ──────────────────────────────────────────────────────────────────────
# OCCUPATION_DISPLAY_LIST
# ──────────────────────────────────────────────────────────────────────

def test_occupation_display_list_is_string():
    assert isinstance(OCCUPATION_DISPLAY_LIST, str)
    assert len(OCCUPATION_DISPLAY_LIST) > 0


def test_occupation_display_list_contains_all_occupations():
    for occ in CANONICAL_OCCUPATIONS:
        assert occ in OCCUPATION_DISPLAY_LIST, (
            f"'{occ}' missing from OCCUPATION_DISPLAY_LIST"
        )


# ──────────────────────────────────────────────────────────────────────
# normalize_occupation never raises
# ──────────────────────────────────────────────────────────────────────

def test_does_not_raise_on_very_long_input():
    """normalize_occupation must not raise on abnormally long input."""
    long_input = "tailor " * 500
    result = normalize_occupation(long_input, MockClient("tailor"))
    assert isinstance(result, OccupationResult)


def test_does_not_raise_on_special_characters():
    """Special characters and emoji in input must not raise."""
    result = normalize_occupation("🪡 टेलर!!! @#$%", MockClient("tailor"))
    assert isinstance(result, OccupationResult)

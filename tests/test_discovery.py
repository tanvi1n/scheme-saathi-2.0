"""
tests/test_discovery.py — Deterministic discovery layer tests.

Tests the normalized-category discovery model introduced in Session 6.

Key invariants:
- Discovery produces CANDIDATE schemes only.
- Discovery does NOT determine eligibility.
- The eligibility engine is a separate step; these tests do not invoke it.
- Every occupation in occupation_to_categories must return a non-empty candidate list.
- Unknown occupations must not crash — they return an empty list or a keyword fallback.
"""

import json
import os
import pytest

from skills.discover import get_candidate_schemes, occupation_to_categories, keyword_map


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def all_schemes():
    """Load the real schemes.json once for the whole module."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    schemes_file = os.path.join(current_dir, "..", "data", "schemes.json")
    with open(schemes_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _ids(candidates: list) -> set:
    """Return the set of scheme IDs from a candidate list."""
    return {s["id"] for s in candidates}


# ──────────────────────────────────────────────────────────────────────
# Category vocabulary tests
# ──────────────────────────────────────────────────────────────────────

ALLOWED_CATEGORIES = {
    "service", "retail", "artisan", "micro_enterprise",
    "manufacturing", "transport", "agriculture",
    "startup", "women_led", "vendor",
}


def test_all_business_schemes_have_normalized_categories(all_schemes):
    """Every business scheme (has target_business_types) must have normalized_categories."""
    for scheme in all_schemes:
        if "target_business_types" in scheme:
            cats = scheme.get("normalized_categories")
            assert cats is not None and len(cats) > 0, (
                f"Business scheme '{scheme['id']}' is missing normalized_categories"
            )


def test_normalized_categories_use_controlled_vocabulary(all_schemes):
    """Every category tag in every scheme must be from the allowed vocabulary."""
    for scheme in all_schemes:
        for cat in scheme.get("normalized_categories", []):
            assert cat in ALLOWED_CATEGORIES, (
                f"Scheme '{scheme['id']}' uses unknown category '{cat}'. "
                f"Allowed: {ALLOWED_CATEGORIES}"
            )


def test_individual_schemes_have_no_normalized_categories(all_schemes):
    """Individual schemes (no target_business_types) should not have normalized_categories."""
    for scheme in all_schemes:
        if "target_business_types" not in scheme:
            assert "normalized_categories" not in scheme, (
                f"Individual scheme '{scheme['id']}' should not have normalized_categories"
            )


def test_occupation_to_categories_uses_controlled_vocabulary():
    """Every category in occupation_to_categories must be from the allowed vocabulary."""
    for occupation, cats in occupation_to_categories.items():
        for cat in cats:
            assert cat in ALLOWED_CATEGORIES, (
                f"Occupation '{occupation}' maps to unknown category '{cat}'"
            )


# ──────────────────────────────────────────────────────────────────────
# Tailor discovery — the core regression tests
# ──────────────────────────────────────────────────────────────────────

def test_tailor_returns_pm_vishwakarma(all_schemes):
    """PM Vishwakarma must be discoverable for tailor (artisan/service/micro_enterprise)."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    assert "pm_vishwakarma" in _ids(candidates), (
        "pm_vishwakarma must be a candidate for 'tailor'"
    )


def test_tailor_returns_mudra_shishu(all_schemes):
    """Mudra Shishu must now be discoverable for tailor via micro_enterprise/service."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    assert "mudra_shishu" in _ids(candidates), (
        "mudra_shishu must be a candidate for 'tailor' — was missed by old keyword model"
    )


def test_tailor_returns_pmegp(all_schemes):
    """PMEGP must be discoverable for tailor via service/micro_enterprise."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    assert "pmegp" in _ids(candidates), (
        "pmegp must be a candidate for 'tailor' — was missed by old keyword model"
    )


def test_tailor_returns_cgtmse(all_schemes):
    """CGTMSE must be discoverable for tailor via service/micro_enterprise."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    assert "cgtmse" in _ids(candidates), (
        "cgtmse must be a candidate for 'tailor' — was missed by old keyword model"
    )


def test_tailor_returns_mudra_kishor(all_schemes):
    """Mudra Kishor must be discoverable for tailor via micro_enterprise/service."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    assert "mudra_kishor" in _ids(candidates), (
        "mudra_kishor must be a candidate for 'tailor'"
    )


def test_tailor_does_not_return_transport_schemes(all_schemes):
    """Transport-only schemes must not be returned for tailor."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    ids = _ids(candidates)
    assert "pm_swarozgar_transport" not in ids, (
        "pm_swarozgar_transport must not be a candidate for 'tailor'"
    )


def test_tailor_does_not_return_vendor_only_schemes(all_schemes):
    """pm_svanidhi (vendor only) must not be returned for tailor."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    assert "pm_svanidhi" not in _ids(candidates), (
        "pm_svanidhi (vendor only) must not be a candidate for 'tailor'"
    )


# ──────────────────────────────────────────────────────────────────────
# Kirana discovery
# ──────────────────────────────────────────────────────────────────────

def test_kirana_returns_retail_schemes(all_schemes):
    """Kirana maps to retail+micro_enterprise; mudra_shishu and cgtmse should appear."""
    candidates = get_candidate_schemes("kirana", all_schemes)
    ids = _ids(candidates)
    assert "mudra_shishu" in ids, "mudra_shishu must be a candidate for 'kirana'"
    assert "cgtmse" in ids, "cgtmse must be a candidate for 'kirana'"


def test_kirana_returns_mudra_kishor(all_schemes):
    """Mudra Kishor (retail trade) must be a candidate for kirana."""
    candidates = get_candidate_schemes("kirana", all_schemes)
    assert "mudra_kishor" in _ids(candidates)


def test_kirana_does_not_return_transport(all_schemes):
    candidates = get_candidate_schemes("kirana", all_schemes)
    assert "pm_swarozgar_transport" not in _ids(candidates)


# ──────────────────────────────────────────────────────────────────────
# Mechanic discovery
# ──────────────────────────────────────────────────────────────────────

def test_mechanic_returns_service_schemes(all_schemes):
    """Mechanic maps to service+micro_enterprise."""
    candidates = get_candidate_schemes("mechanic", all_schemes)
    ids = _ids(candidates)
    assert "mudra_shishu" in ids, "mudra_shishu must be a candidate for 'mechanic'"
    assert "pmegp" in ids, "pmegp must be a candidate for 'mechanic'"


def test_mechanic_does_not_return_vendor_only(all_schemes):
    candidates = get_candidate_schemes("mechanic", all_schemes)
    assert "pm_svanidhi" not in _ids(candidates)


# ──────────────────────────────────────────────────────────────────────
# Auto / taxi driver discovery
# ──────────────────────────────────────────────────────────────────────

def test_auto_driver_returns_transport_schemes(all_schemes):
    """auto_driver maps only to transport; pm_swarozgar_transport must appear."""
    candidates = get_candidate_schemes("auto_driver", all_schemes)
    assert "pm_swarozgar_transport" in _ids(candidates), (
        "pm_swarozgar_transport must be a candidate for 'auto_driver'"
    )


def test_taxi_driver_returns_transport_schemes(all_schemes):
    candidates = get_candidate_schemes("taxi_driver", all_schemes)
    assert "pm_swarozgar_transport" in _ids(candidates)


def test_auto_driver_does_not_return_artisan_schemes(all_schemes):
    """pm_vishwakarma (artisan) must not appear for auto_driver."""
    candidates = get_candidate_schemes("auto_driver", all_schemes)
    assert "pm_vishwakarma" not in _ids(candidates)


# ──────────────────────────────────────────────────────────────────────
# Street vendor discovery
# ──────────────────────────────────────────────────────────────────────

def test_street_vendor_returns_pm_svanidhi(all_schemes):
    """pm_svanidhi is tagged vendor; street_vendor maps to vendor."""
    candidates = get_candidate_schemes("street_vendor", all_schemes)
    assert "pm_svanidhi" in _ids(candidates), (
        "pm_svanidhi must be a candidate for 'street_vendor'"
    )


def test_street_vendor_also_returns_micro_enterprise_schemes(all_schemes):
    """mudra_shishu (micro_enterprise+vendor) must appear for street_vendor."""
    candidates = get_candidate_schemes("street_vendor", all_schemes)
    assert "mudra_shishu" in _ids(candidates)


# ──────────────────────────────────────────────────────────────────────
# Salon discovery
# ──────────────────────────────────────────────────────────────────────

def test_salon_returns_service_and_artisan_schemes(all_schemes):
    """salon maps to service+artisan+micro_enterprise."""
    candidates = get_candidate_schemes("salon", all_schemes)
    ids = _ids(candidates)
    assert "pm_vishwakarma" in ids, "pm_vishwakarma (artisan) must be a candidate for 'salon'"
    assert "mudra_shishu" in ids, "mudra_shishu (service) must be a candidate for 'salon'"


# ──────────────────────────────────────────────────────────────────────
# Carpenter discovery
# ──────────────────────────────────────────────────────────────────────

def test_carpenter_returns_artisan_schemes(all_schemes):
    candidates = get_candidate_schemes("carpenter", all_schemes)
    assert "pm_vishwakarma" in _ids(candidates)


# ──────────────────────────────────────────────────────────────────────
# Unknown / unrecognised occupation — graceful fallback
# ──────────────────────────────────────────────────────────────────────

def test_unknown_occupation_returns_list_not_error(all_schemes):
    """An unrecognised occupation must return a list (possibly empty), not raise."""
    result = get_candidate_schemes("underwater_welder", all_schemes)
    assert isinstance(result, list), "get_candidate_schemes must always return a list"


def test_unknown_occupation_returns_empty_list(all_schemes):
    """An occupation with no keyword fallback and no category match returns []."""
    result = get_candidate_schemes("underwater_welder", all_schemes)
    assert result == [], (
        "Completely unknown occupation should return empty list, not crash"
    )


def test_empty_string_occupation_returns_list_not_error(all_schemes):
    """Empty string input must not raise an exception."""
    result = get_candidate_schemes("", all_schemes)
    assert isinstance(result, list)


# ──────────────────────────────────────────────────────────────────────
# Discovery does NOT determine eligibility
# ──────────────────────────────────────────────────────────────────────

def test_candidates_include_schemes_that_may_fail_eligibility(all_schemes):
    """
    stand_up_india requires female gender and sc/st caste.
    A tailor (no profile) still gets it as a CANDIDATE because
    discovery does not evaluate eligibility rules.
    The eligibility engine will filter it out for a male/general user.
    """
    candidates = get_candidate_schemes("tailor", all_schemes)
    # stand_up_india has categories service+retail+manufacturing+startup
    # tailor maps to artisan+service+micro_enterprise → service is the overlap
    # It should appear as a candidate regardless of the user's gender/caste
    assert "stand_up_india" in _ids(candidates), (
        "stand_up_india must be a candidate for 'tailor' — "
        "eligibility (gender/caste) is the engine's job, not discovery's"
    )


def test_get_candidate_schemes_returns_dicts_not_eligibility_results(all_schemes):
    """Return value must be a list of scheme dicts, not EligibilityResult objects."""
    candidates = get_candidate_schemes("tailor", all_schemes)
    for item in candidates:
        assert isinstance(item, dict), "Each candidate must be a scheme dict"
        assert "id" in item, "Each candidate dict must have an 'id' field"
        assert "eligibility_criteria" not in item or isinstance(
            item["eligibility_criteria"], dict
        ), "eligibility_criteria must be the raw scheme data, not an EligibilityResult"


def test_get_candidate_schemes_does_not_import_eligibility_engine():
    """
    Verify that get_candidate_schemes has no import dependency on the
    eligibility engine. The function must be pure discovery.
    """
    import skills.discover as discover_module
    # Check that eligibility_engine is not imported at module level
    assert not hasattr(discover_module, "check_scheme_eligibility"), (
        "skills/discover.py must not import check_scheme_eligibility — "
        "discovery and eligibility must be separate layers"
    )
    assert not hasattr(discover_module, "EligibilityStatus"), (
        "skills/discover.py must not import EligibilityStatus"
    )
    assert not hasattr(discover_module, "eligibility_engine"), (
        "skills/discover.py must not import eligibility_engine"
    )


# ──────────────────────────────────────────────────────────────────────
# All canonical occupations return non-empty candidates
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("occupation", list(occupation_to_categories.keys()))
def test_all_canonical_occupations_return_candidates(occupation, all_schemes):
    """Every occupation in occupation_to_categories must return at least one candidate."""
    candidates = get_candidate_schemes(occupation, all_schemes)
    assert len(candidates) > 0, (
        f"Occupation '{occupation}' returned no candidates. "
        f"Check that its categories {occupation_to_categories[occupation]} "
        f"match at least one scheme's normalized_categories."
    )

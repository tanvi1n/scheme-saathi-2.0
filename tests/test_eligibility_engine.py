"""
tests/test_eligibility_engine.py

Behavioral tests for eligibility_engine.py.

These tests use scheme dicts defined inline — no file I/O, no Telegram,
no LLM. Each test maps to a scenario from the baseline test plan.

Run with:  python -m pytest tests/test_eligibility_engine.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from eligibility_engine import (
    UNKNOWN,
    UserProfile,
    EligibilityStatus,
    check_scheme_eligibility,
    filter_schemes_by_eligibility,
)

# ──────────────────────────────────────────────────────────────────────
# Shared scheme fixtures
# ──────────────────────────────────────────────────────────────────────

def scheme_any():
    """Generic scheme with no restrictions — everything 'any'/false."""
    return {
        "id": "test_any",
        "name": "Test Any Scheme",
        "telugu_name": "టెస్ట్ పథకం",
        "eligibility_criteria": {
            "gender": "any",
            "caste": "any",
            "age_min": 18,
            "age_max": None,
            "gst_required": False,
            "bank_account_required": False,
        },
        "special_requirements": [],
    }

def scheme_female_only():
    s = scheme_any()
    s["id"] = "test_female"
    s["eligibility_criteria"]["gender"] = "female"
    return s

def scheme_sc_st_only():
    s = scheme_any()
    s["id"] = "test_sc_st"
    s["eligibility_criteria"]["caste"] = "sc/st"
    return s

def scheme_age_18_45():
    s = scheme_any()
    s["id"] = "test_age_18_45"
    s["eligibility_criteria"]["age_min"] = 18
    s["eligibility_criteria"]["age_max"] = 45
    return s

def scheme_gst_required():
    s = scheme_any()
    s["id"] = "test_gst"
    s["eligibility_criteria"]["gst_required"] = True
    return s

def scheme_bank_required():
    s = scheme_any()
    s["id"] = "test_bank"
    s["eligibility_criteria"]["bank_account_required"] = True
    return s

def scheme_land_required():
    s = scheme_any()
    s["id"] = "test_land"
    s["special_requirements"] = [
        {"field": "land_ownership", "type": "boolean_required",
         "label": "land_ownership", "failure_reason": "Land ownership required"}
    ]
    return s

def scheme_white_ration_required():
    s = scheme_any()
    s["id"] = "test_ration"
    s["special_requirements"] = [
        {"field": "white_ration_card", "type": "boolean_required",
         "label": "white_ration_card", "failure_reason": "White ration card required"}
    ]
    return s

def scheme_max_income_200k():
    s = scheme_any()
    s["id"] = "test_income"
    s["special_requirements"] = [
        {"field": "annual_income", "type": "max_value", "max": 200000,
         "label": "annual_income", "failure_reason": "Income must be <= 200000"}
    ]
    return s

def scheme_max_units_200():
    s = scheme_any()
    s["id"] = "test_units"
    s["special_requirements"] = [
        {"field": "monthly_units", "type": "max_value", "max": 200,
         "label": "monthly_units", "failure_reason": "Monthly units must be <= 200"}
    ]
    return s

def scheme_max_turnover_200k():
    s = scheme_any()
    s["id"] = "test_turnover"
    s["special_requirements"] = [
        {"field": "annual_turnover", "type": "max_value", "max": 200000,
         "label": "annual_turnover", "failure_reason": "Turnover must be <= 200000"}
    ]
    return s

def scheme_sc_st_any_caste():
    """stand_up_india-style: caste='sc/st/any' with 'any' token."""
    s = scheme_any()
    s["id"] = "test_sc_st_any"
    s["eligibility_criteria"]["gender"] = "female"
    s["eligibility_criteria"]["caste"] = "sc/st/any"
    return s


# ──────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────

def ELIGIBLE(result):
    return result.status == EligibilityStatus.LIKELY_ELIGIBLE

def NEEDS_VERIF(result):
    return result.status == EligibilityStatus.NEEDS_VERIFICATION

def NOT_ELIGIBLE(result):
    return result.status == EligibilityStatus.LIKELY_NOT_ELIGIBLE


# ──────────────────────────────────────────────────────────────────────
# UNKNOWN sentinel tests
# ──────────────────────────────────────────────────────────────────────

def test_unknown_is_singleton():
    from eligibility_engine import _UnknownType
    a = _UnknownType()
    b = _UnknownType()
    assert a is b

def test_unknown_bool_raises():
    with pytest.raises(TypeError):
        bool(UNKNOWN)

def test_unknown_repr():
    assert repr(UNKNOWN) == "UNKNOWN"


# ──────────────────────────────────────────────────────────────────────
# M1-equivalent: basic eligible business user
# ──────────────────────────────────────────────────────────────────────

def test_basic_eligible_business_user():
    """Tailor, male, general, 30, no GST needed, bank yes → LIKELY_ELIGIBLE."""
    profile = UserProfile(
        gender="male", caste="general", age=30,
        has_gst=False, has_bank_account=True,
    )
    result = check_scheme_eligibility(profile, scheme_any())
    assert ELIGIBLE(result)
    assert result.failed == []
    assert result.unknown == []
    assert result.missing_fields == []


# ──────────────────────────────────────────────────────────────────────
# M2-equivalent: basic eligible individual user
# ──────────────────────────────────────────────────────────────────────

def test_basic_eligible_individual_user():
    """Female, SC, 25, white ration card yes, bank yes → LIKELY_ELIGIBLE."""
    profile = UserProfile(
        gender="female", caste="sc", age=25,
        has_bank_account=True, white_ration_card=True,
    )
    result = check_scheme_eligibility(profile, scheme_any())
    assert ELIGIBLE(result)


# ──────────────────────────────────────────────────────────────────────
# Age checks
# ──────────────────────────────────────────────────────────────────────

def test_age_below_minimum():
    profile = UserProfile(gender="male", caste="general", age=17, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_age_18_45())
    assert NOT_ELIGIBLE(result)
    fields = [d.field for d in result.failed]
    assert "age_min" in fields

def test_age_at_minimum():
    profile = UserProfile(gender="male", caste="general", age=18, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_age_18_45())
    assert ELIGIBLE(result)

def test_age_above_maximum():
    profile = UserProfile(gender="male", caste="general", age=46, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_age_18_45())
    assert NOT_ELIGIBLE(result)
    fields = [d.field for d in result.failed]
    assert "age_max" in fields

def test_age_at_maximum():
    profile = UserProfile(gender="male", caste="general", age=45, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_age_18_45())
    assert ELIGIBLE(result)

def test_age_max_null_no_upper_limit():
    """age_max=None → no upper bound, any age >= min passes."""
    profile = UserProfile(gender="male", caste="general", age=80, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_any())  # age_max=None
    assert ELIGIBLE(result)

def test_age_unknown_needs_verification():
    profile = UserProfile(gender="male", caste="general", age=UNKNOWN, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_age_18_45())
    assert NEEDS_VERIF(result)
    assert "age" in result.missing_fields


# ──────────────────────────────────────────────────────────────────────
# Gender checks
# ──────────────────────────────────────────────────────────────────────

def test_gender_mismatch():
    profile = UserProfile(gender="male", caste="general", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_female_only())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "gender" for d in result.failed)

def test_gender_match():
    profile = UserProfile(gender="female", caste="general", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_female_only())
    assert ELIGIBLE(result)

def test_gender_unknown_needs_verification():
    profile = UserProfile(gender=UNKNOWN, caste="general", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_female_only())
    assert NEEDS_VERIF(result)
    assert "gender" in result.missing_fields

def test_gender_any_passes_all():
    for g in ["male", "female", "other"]:
        profile = UserProfile(gender=g, caste="general", age=25, has_bank_account=False)
        result = check_scheme_eligibility(profile, scheme_any())
        assert ELIGIBLE(result), f"gender={g} should pass any-gender scheme"


# ──────────────────────────────────────────────────────────────────────
# Caste checks
# ──────────────────────────────────────────────────────────────────────

def test_caste_mismatch():
    profile = UserProfile(gender="male", caste="general", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_sc_st_only())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "caste" for d in result.failed)

def test_caste_match_single():
    profile = UserProfile(gender="male", caste="sc", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_sc_st_only())
    assert ELIGIBLE(result)

def test_caste_multivalue_sc_matches_sc_st():
    """M3: user caste 'sc' matches scheme caste 'sc/st'."""
    profile = UserProfile(gender="male", caste="sc", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_sc_st_only())
    assert ELIGIBLE(result)

def test_caste_multivalue_st_matches_sc_st():
    profile = UserProfile(gender="male", caste="st", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_sc_st_only())
    assert ELIGIBLE(result)

def test_caste_multivalue_general_fails_sc_st():
    profile = UserProfile(gender="male", caste="general", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_sc_st_only())
    assert NOT_ELIGIBLE(result)

def test_caste_any_token_passes_all_castes():
    """stand_up_india-style 'sc/st/any': any caste passes due to 'any' token."""
    for caste in ["general", "sc", "st", "obc", "minority"]:
        profile = UserProfile(gender="female", caste=caste, age=25, has_bank_account=False)
        result = check_scheme_eligibility(profile, scheme_sc_st_any_caste())
        # Caste should pass (any token). Gender is female so that passes too.
        assert ELIGIBLE(result), f"caste={caste} should pass sc/st/any scheme for female user"

def test_caste_unknown_needs_verification():
    profile = UserProfile(gender="male", caste=UNKNOWN, age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_sc_st_only())
    assert NEEDS_VERIF(result)
    assert "caste" in result.missing_fields


# ──────────────────────────────────────────────────────────────────────
# GST checks
# ──────────────────────────────────────────────────────────────────────

def test_gst_required_user_has_gst():
    profile = UserProfile(gender="male", caste="general", age=30, has_gst=True)
    result = check_scheme_eligibility(profile, scheme_gst_required())
    assert ELIGIBLE(result)

def test_gst_required_user_no_gst():
    profile = UserProfile(gender="male", caste="general", age=30, has_gst=False)
    result = check_scheme_eligibility(profile, scheme_gst_required())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "gst" for d in result.failed)

def test_gst_required_unknown_needs_verification():
    profile = UserProfile(gender="male", caste="general", age=30, has_gst=UNKNOWN)
    result = check_scheme_eligibility(profile, scheme_gst_required())
    assert NEEDS_VERIF(result)
    assert "gst" in result.missing_fields

def test_gst_not_required_passes_regardless():
    for gst_val in [True, False, UNKNOWN]:
        profile = UserProfile(gender="male", caste="general", age=30, has_gst=gst_val)
        result = check_scheme_eligibility(profile, scheme_any())
        # gst not required → always passes that check
        gst_check = next((d for d in result.passed if d.field == "gst"), None)
        assert gst_check is not None and gst_check.passed, \
            f"gst check should pass when not required (has_gst={gst_val!r})"


# ──────────────────────────────────────────────────────────────────────
# Bank account checks
# ──────────────────────────────────────────────────────────────────────

def test_bank_required_user_has_bank():
    profile = UserProfile(gender="male", caste="general", age=30, has_bank_account=True)
    result = check_scheme_eligibility(profile, scheme_bank_required())
    assert ELIGIBLE(result)

def test_bank_required_user_no_bank():
    profile = UserProfile(gender="male", caste="general", age=30, has_bank_account=False)
    result = check_scheme_eligibility(profile, scheme_bank_required())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "bank_account" for d in result.failed)

def test_bank_required_unknown_needs_verification():
    profile = UserProfile(gender="male", caste="general", age=30, has_bank_account=UNKNOWN)
    result = check_scheme_eligibility(profile, scheme_bank_required())
    assert NEEDS_VERIF(result)
    assert "bank_account" in result.missing_fields


# ──────────────────────────────────────────────────────────────────────
# Special requirements: boolean_required (land_ownership, white_ration_card)
# ──────────────────────────────────────────────────────────────────────

def test_land_ownership_unknown_needs_verification():
    """M7-variant: land not yet collected → NEEDS_VERIFICATION, not ineligible."""
    profile = UserProfile(
        gender="male", caste="general", age=40,
        has_bank_account=True, land_ownership=UNKNOWN
    )
    result = check_scheme_eligibility(profile, scheme_land_required())
    assert NEEDS_VERIF(result)
    assert "land_ownership" in result.missing_fields
    assert result.unknown[0].is_unknown is True

def test_land_ownership_false_not_eligible():
    """M7: user explicitly has no land → LIKELY_NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="male", caste="general", age=40,
        has_bank_account=True, land_ownership=False
    )
    result = check_scheme_eligibility(profile, scheme_land_required())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "land_ownership" for d in result.failed)
    # Critically: is_unknown must be False — this is a hard fail, not missing data
    land_fail = next(d for d in result.failed if d.field == "land_ownership")
    assert land_fail.is_unknown is False

def test_land_ownership_true_eligible():
    """M7: user has land → eligible."""
    profile = UserProfile(
        gender="male", caste="general", age=40,
        has_bank_account=True, land_ownership=True
    )
    result = check_scheme_eligibility(profile, scheme_land_required())
    assert ELIGIBLE(result)

def test_white_ration_card_required_missing():
    profile = UserProfile(
        gender="female", caste="any", age=30,
        white_ration_card=UNKNOWN
    )
    result = check_scheme_eligibility(profile, scheme_white_ration_required())
    assert NEEDS_VERIF(result)
    assert "white_ration_card" in result.missing_fields

def test_white_ration_card_required_false():
    profile = UserProfile(
        gender="female", caste="general", age=30,
        white_ration_card=False
    )
    result = check_scheme_eligibility(profile, scheme_white_ration_required())
    assert NOT_ELIGIBLE(result)

def test_white_ration_card_required_true():
    profile = UserProfile(
        gender="female", caste="general", age=30,
        white_ration_card=True
    )
    result = check_scheme_eligibility(profile, scheme_white_ration_required())
    assert ELIGIBLE(result)


# ──────────────────────────────────────────────────────────────────────
# Special requirements: max_value (income, units, turnover)
# ──────────────────────────────────────────────────────────────────────

def test_max_income_within_limit():
    profile = UserProfile(gender="female", caste="sc", age=25, annual_income=150000)
    result = check_scheme_eligibility(profile, scheme_max_income_200k())
    assert ELIGIBLE(result)

def test_max_income_at_boundary():
    profile = UserProfile(gender="female", caste="sc", age=25, annual_income=200000)
    result = check_scheme_eligibility(profile, scheme_max_income_200k())
    assert ELIGIBLE(result)

def test_max_income_exceeded():
    profile = UserProfile(gender="female", caste="sc", age=25, annual_income=200001)
    result = check_scheme_eligibility(profile, scheme_max_income_200k())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "annual_income" for d in result.failed)

def test_max_income_unknown_needs_verification():
    """M11-variant: income not collected → NEEDS_VERIFICATION."""
    profile = UserProfile(gender="female", caste="sc", age=25, annual_income=UNKNOWN)
    result = check_scheme_eligibility(profile, scheme_max_income_200k())
    assert NEEDS_VERIF(result)
    assert "annual_income" in result.missing_fields

def test_max_units_within_limit():
    profile = UserProfile(gender="any", caste="any", age=30, monthly_units=150)
    result = check_scheme_eligibility(profile, scheme_max_units_200())
    assert ELIGIBLE(result)

def test_max_units_exceeded():
    profile = UserProfile(gender="male", caste="general", age=30, monthly_units=201)
    result = check_scheme_eligibility(profile, scheme_max_units_200())
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "monthly_units" for d in result.failed)

def test_max_turnover_within_limit():
    profile = UserProfile(gender="male", caste="sc", age=25, annual_turnover=100000)
    result = check_scheme_eligibility(profile, scheme_max_turnover_200k())
    assert ELIGIBLE(result)

def test_max_turnover_exceeded():
    profile = UserProfile(gender="male", caste="sc", age=25, annual_turnover=250000)
    result = check_scheme_eligibility(profile, scheme_max_turnover_200k())
    assert NOT_ELIGIBLE(result)

def test_max_turnover_unknown_needs_verification():
    profile = UserProfile(gender="male", caste="sc", age=25, annual_turnover=UNKNOWN)
    result = check_scheme_eligibility(profile, scheme_max_turnover_200k())
    assert NEEDS_VERIF(result)
    assert "annual_turnover" in result.missing_fields


# ──────────────────────────────────────────────────────────────────────
# Result structure integrity
# ──────────────────────────────────────────────────────────────────────

def test_result_carries_scheme_id_and_name():
    profile = UserProfile(gender="male", caste="general", age=30)
    s = scheme_any()
    s["id"] = "my_scheme_id"
    s["telugu_name"] = "నా పథకం"
    result = check_scheme_eligibility(profile, s)
    assert result.scheme_id == "my_scheme_id"
    assert result.scheme_name == "నా పథకం"

def test_failed_details_have_is_unknown_false():
    """Hard failures must not be marked as unknown."""
    profile = UserProfile(gender="male", caste="general", age=17)
    result = check_scheme_eligibility(profile, scheme_age_18_45())
    for d in result.failed:
        assert d.is_unknown is False, f"{d.field} failed but is_unknown=True — incorrect"

def test_unknown_details_have_is_unknown_true():
    profile = UserProfile(gender=UNKNOWN, caste="general", age=30)
    result = check_scheme_eligibility(profile, scheme_female_only())
    for d in result.unknown:
        assert d.is_unknown is True

def test_missing_fields_matches_unknown_fields():
    profile = UserProfile(gender=UNKNOWN, caste=UNKNOWN, age=30)
    result = check_scheme_eligibility(profile, scheme_female_only())
    unknown_field_names = {d.field for d in result.unknown}
    assert set(result.missing_fields) == unknown_field_names

def test_failed_takes_priority_over_unknown():
    """If there is a hard failure AND unknown fields, status is NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="male",       # fails female-only scheme
        caste=UNKNOWN,       # unknown
        age=30,
        has_bank_account=UNKNOWN,  # unknown
    )
    s = scheme_female_only()
    s["eligibility_criteria"]["bank_account_required"] = True
    result = check_scheme_eligibility(profile, s)
    assert NOT_ELIGIBLE(result), \
        "Hard gender failure should dominate even with unknown fields present"


# ──────────────────────────────────────────────────────────────────────
# filter_schemes_by_eligibility
# ──────────────────────────────────────────────────────────────────────

def test_filter_groups_correctly():
    profile = UserProfile(gender="male", caste="general", age=30,
                          has_gst=False, has_bank_account=True)
    schemes = [
        scheme_any(),                # should be LIKELY_ELIGIBLE
        scheme_female_only(),        # should be LIKELY_NOT_ELIGIBLE (male user)
        scheme_land_required(),      # should be NEEDS_VERIFICATION (land=UNKNOWN)
    ]
    groups = filter_schemes_by_eligibility(profile, schemes)
    assert len(groups["likely_eligible"])     == 1
    assert len(groups["needs_verification"])  == 1
    assert len(groups["likely_not_eligible"]) == 1
    assert groups["likely_eligible"][0][0]["id"]     == "test_any"
    assert groups["needs_verification"][0][0]["id"]  == "test_land"
    assert groups["likely_not_eligible"][0][0]["id"] == "test_female"


# ──────────────────────────────────────────────────────────────────────
# Regression against real schemes.json data
# ──────────────────────────────────────────────────────────────────────

def load_scheme(scheme_id: str) -> dict:
    import json, os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "schemes.json")
    with open(path, "r", encoding="utf-8") as f:
        schemes = json.load(f)
    return next(s for s in schemes if s["id"] == scheme_id)


def test_real_pm_vishwakarma_tailor_eligible():
    """M1: tailor, male, general, 30, no GST, yes bank → eligible."""
    profile = UserProfile(
        gender="male", caste="general", age=30,
        has_gst=False, has_bank_account=True,
    )
    result = check_scheme_eligibility(profile, load_scheme("pm_vishwakarma"))
    assert ELIGIBLE(result)


def test_real_rythu_bharosa_land_unknown():
    """M7-variant: land not collected → NEEDS_VERIFICATION."""
    profile = UserProfile(
        gender="male", caste="general", age=40,
        has_bank_account=True, land_ownership=UNKNOWN,
    )
    result = check_scheme_eligibility(profile, load_scheme("rythu_bharosa"))
    assert NEEDS_VERIF(result)
    assert "land_ownership" in result.missing_fields


def test_real_rythu_bharosa_no_land():
    """M7: user says no land → LIKELY_NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="male", caste="general", age=40,
        has_bank_account=True, land_ownership=False,
    )
    result = check_scheme_eligibility(profile, load_scheme("rythu_bharosa"))
    assert NOT_ELIGIBLE(result)


def test_real_kalyana_lakshmi_income_over_limit():
    """kalyana_lakshmi: income 250000 > 200000 → NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="female", caste="sc", age=22,
        has_bank_account=True, annual_income=250000,
    )
    result = check_scheme_eligibility(profile, load_scheme("kalyana_lakshmi"))
    assert NOT_ELIGIBLE(result)


def test_real_kalyana_lakshmi_income_unknown():
    """kalyana_lakshmi: income not collected → NEEDS_VERIFICATION."""
    profile = UserProfile(
        gender="female", caste="sc", age=22,
        has_bank_account=True, annual_income=UNKNOWN,
    )
    result = check_scheme_eligibility(profile, load_scheme("kalyana_lakshmi"))
    assert NEEDS_VERIF(result)
    assert "annual_income" in result.missing_fields


def test_real_gruha_jyothi_units_exceeded():
    """gruha_jyothi: monthly_units 201 > 200 → NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="male", caste="general", age=35,
        has_bank_account=False, monthly_units=201,
    )
    result = check_scheme_eligibility(profile, load_scheme("gruha_jyothi"))
    assert NOT_ELIGIBLE(result)


def test_real_gruha_jyothi_units_within_limit():
    profile = UserProfile(
        gender="male", caste="general", age=35,
        has_bank_account=False, monthly_units=150,
    )
    result = check_scheme_eligibility(profile, load_scheme("gruha_jyothi"))
    assert ELIGIBLE(result)


def test_real_t_pride_sc_matches_sc_st():
    """t_pride caste='sc/st': user caste 'sc' should match."""
    profile = UserProfile(
        gender="male", caste="sc", age=30,
        has_gst=True, has_bank_account=True,
    )
    result = check_scheme_eligibility(profile, load_scheme("t_pride"))
    assert ELIGIBLE(result)


def test_real_t_pride_general_fails_sc_st():
    """t_pride caste='sc/st': user caste 'general' should fail."""
    profile = UserProfile(
        gender="male", caste="general", age=30,
        has_gst=True, has_bank_account=True,
    )
    result = check_scheme_eligibility(profile, load_scheme("t_pride"))
    assert NOT_ELIGIBLE(result)


def test_real_mahalakshmi_no_ration_card():
    """mahalakshmi: white_ration_card=False → NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="female", caste="general", age=30,
        has_bank_account=True, white_ration_card=False,
    )
    result = check_scheme_eligibility(profile, load_scheme("mahalakshmi_scheme"))
    assert NOT_ELIGIBLE(result)


def test_real_we_hub_male_not_eligible():
    """we_hub is female-only: male → NOT_ELIGIBLE."""
    profile = UserProfile(
        gender="male", caste="general", age=28,
        has_gst=False, has_bank_account=True,
    )
    result = check_scheme_eligibility(profile, load_scheme("we_hub"))
    assert NOT_ELIGIBLE(result)
    assert any(d.field == "gender" for d in result.failed)

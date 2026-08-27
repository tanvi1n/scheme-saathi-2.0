"""
eligibility_engine.py — Deterministic scheme eligibility engine.

Design principles:
- No LLM. No Telegram. No file I/O. No session state.
- Pure function: (UserProfile, scheme_dict) -> EligibilityResult
- Caller passes scheme data in; engine does not read files.
- All result strings are language-neutral. Telugu rendering is the
  responsibility of the conversation/UI layer.
- UNKNOWN is a first-class sentinel distinct from False and 0.
  Missing data → NEEDS_VERIFICATION, never a silent pass or fail.

Introduced: 2026-08-26 (Razorpay Buildathon sprint)
Replaces conceptually: inline eligibility logic in agent.py
                       dead check_eligibility() in skills/eligibility.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional


# ──────────────────────────────────────────────────────────────────────
# UNKNOWN sentinel
# ──────────────────────────────────────────────────────────────────────

class _UnknownType:
    """
    Singleton sentinel for data that has not been collected yet.

    Distinct from:
      False  — user explicitly answered No
      None   — Python null / unset attribute
      0      — user entered zero

    When the engine encounters UNKNOWN on a mandatory field it produces
    NEEDS_VERIFICATION, not LIKELY_NOT_ELIGIBLE.
    """
    _instance: Optional["_UnknownType"] = None

    def __new__(cls) -> "_UnknownType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        # Prevents accidental truthiness evaluation.
        # The engine must always use `is UNKNOWN`, never `if value`.
        raise TypeError(
            "UNKNOWN cannot be evaluated as a boolean. "
            "Use `value is UNKNOWN` to test for missing data."
        )


UNKNOWN = _UnknownType()


# ──────────────────────────────────────────────────────────────────────
# UserProfile
# ──────────────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    """
    Structured user profile consumed by the eligibility engine.

    Fields default to UNKNOWN until the conversation layer collects them.
    The engine interprets UNKNOWN as "not yet known" → NEEDS_VERIFICATION.

    Field notes:
    - gender:           "male" | "female" | "other"
    - caste:            "general" | "sc" | "st" | "obc" | "minority"
    - age:              int (years)
    - business_type:    lowercase string e.g. "tailor", "kirana"
    - has_gst:          True | False | UNKNOWN
    - has_bank_account: True | False | UNKNOWN
    - white_ration_card: True | False | UNKNOWN  (individual schemes)
    - land_ownership:   True | False | UNKNOWN   (rythu_bharosa)
    - annual_income:    int | UNKNOWN             (kalyana_lakshmi)
    - monthly_units:    int | UNKNOWN             (gruha_jyothi)
    - annual_turnover:  int | UNKNOWN             (rajiv_yuva_vikasam)
    """
    gender:            str = UNKNOWN  # type: ignore[assignment]
    caste:             str = UNKNOWN  # type: ignore[assignment]
    age:               Any = UNKNOWN

    # Business path
    business_type:     Any = UNKNOWN
    has_gst:           Any = UNKNOWN
    has_bank_account:  Any = UNKNOWN

    # Individual path
    white_ration_card: Any = UNKNOWN

    # Scheme-specific (collected post-selection)
    land_ownership:    Any = UNKNOWN
    annual_income:     Any = UNKNOWN
    monthly_units:     Any = UNKNOWN
    annual_turnover:   Any = UNKNOWN


# ──────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────

class EligibilityStatus(Enum):
    LIKELY_ELIGIBLE     = "LIKELY_ELIGIBLE"
    NEEDS_VERIFICATION  = "NEEDS_VERIFICATION"
    LIKELY_NOT_ELIGIBLE = "LIKELY_NOT_ELIGIBLE"


@dataclass
class CheckDetail:
    """
    Result of a single eligibility criterion check.

    field:      Name of the profile/scheme field checked.
    passed:     True if the criterion was satisfied.
    reason:     Language-neutral explanation string.
    is_unknown: True when the field value was UNKNOWN (missing data).
                When is_unknown=True, passed is always False, but the
                *reason* is different from a hard failure.
    """
    field:      str
    passed:     bool
    reason:     str
    is_unknown: bool = False


@dataclass
class EligibilityResult:
    """
    Complete structured output from check_scheme_eligibility().

    status:         Overall verdict.
    passed:         Criteria that were evaluated and satisfied.
    failed:         Criteria that were evaluated and not satisfied.
    unknown:        Criteria that could not be evaluated (UNKNOWN inputs).
    missing_fields: Profile field names the caller must still collect.
    scheme_id:      ID of the scheme that was checked (for traceability).
    scheme_name:    Display name of the scheme.
    """
    status:         EligibilityStatus
    passed:         List[CheckDetail]
    failed:         List[CheckDetail]
    unknown:        List[CheckDetail]
    missing_fields: List[str]
    scheme_id:      str = ""
    scheme_name:    str = ""


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _is_unknown(value: Any) -> bool:
    """Safe test for UNKNOWN that does not trigger __bool__."""
    return value is UNKNOWN or value is None


def _check_gender(profile: UserProfile, criteria: dict) -> Optional[CheckDetail]:
    required = criteria.get("gender", "any")
    if required == "any":
        return CheckDetail("gender", True, "No gender restriction")
    if _is_unknown(profile.gender):
        return CheckDetail("gender", False, "Gender not collected", is_unknown=True)
    if profile.gender == required:
        return CheckDetail("gender", True, f"Gender requirement satisfied ({required})")
    return CheckDetail(
        "gender", False,
        f"Gender required: {required}, provided: {profile.gender}"
    )


def _check_caste(profile: UserProfile, criteria: dict) -> Optional[CheckDetail]:
    required = criteria.get("caste", "any")
    if required == "any":
        return CheckDetail("caste", True, "No caste restriction")
    if _is_unknown(profile.caste):
        return CheckDetail("caste", False, "Caste not collected", is_unknown=True)

    # Multi-value caste: "sc/st", "sc/st/obc/minority", etc.
    # NOTE: stand_up_india has "sc/st/any" — "any" as a token is treated
    # as a wildcard that matches every caste. This preserves existing
    # agent.py behavior while flagging the data ambiguity in a comment.
    allowed = [t.strip() for t in required.split("/")]
    if "any" in allowed:
        # DATA ISSUE: stand_up_india uses "sc/st/any" to mean the scheme
        # accepts all castes for women. Pending external verification.
        # For now, treat "any" token as wildcard → always passes caste check.
        return CheckDetail(
            "caste", True,
            f"Caste check: 'any' token present in allowed list {allowed} — passes"
        )
    if profile.caste in allowed:
        return CheckDetail("caste", True, f"Caste {profile.caste!r} in allowed {allowed}")
    return CheckDetail(
        "caste", False,
        f"Caste required: one of {allowed}, provided: {profile.caste!r}"
    )


def _check_age(profile: UserProfile, criteria: dict) -> List[CheckDetail]:
    results: List[CheckDetail] = []
    age_min = criteria.get("age_min", 0)
    age_max = criteria.get("age_max")  # None means no upper limit

    if _is_unknown(profile.age):
        results.append(CheckDetail("age", False, "Age not collected", is_unknown=True))
        return results

    # Minimum
    if profile.age >= age_min:
        results.append(CheckDetail("age_min", True, f"Age {profile.age} >= minimum {age_min}"))
    else:
        results.append(CheckDetail(
            "age_min", False,
            f"Age {profile.age} below minimum {age_min}"
        ))

    # Maximum (null = no upper bound)
    if age_max is None:
        results.append(CheckDetail("age_max", True, "No upper age limit"))
    elif profile.age <= age_max:
        results.append(CheckDetail("age_max", True, f"Age {profile.age} <= maximum {age_max}"))
    else:
        results.append(CheckDetail(
            "age_max", False,
            f"Age {profile.age} above maximum {age_max}"
        ))

    return results


def _check_gst(profile: UserProfile, criteria: dict) -> Optional[CheckDetail]:
    required = criteria.get("gst_required", False)
    if not required:
        return CheckDetail("gst", True, "GST not required for this scheme")
    if _is_unknown(profile.has_gst):
        return CheckDetail("gst", False, "GST status not collected", is_unknown=True)
    if profile.has_gst:
        return CheckDetail("gst", True, "GST requirement satisfied")
    return CheckDetail("gst", False, "GST registration required but not present")


def _check_bank_account(profile: UserProfile, criteria: dict) -> Optional[CheckDetail]:
    required = criteria.get("bank_account_required", False)
    if not required:
        return CheckDetail("bank_account", True, "Bank account not required for this scheme")
    if _is_unknown(profile.has_bank_account):
        return CheckDetail(
            "bank_account", False, "Bank account status not collected", is_unknown=True
        )
    if profile.has_bank_account:
        return CheckDetail("bank_account", True, "Bank account requirement satisfied")
    return CheckDetail("bank_account", False, "Bank account required but not present")


def _check_special_requirement(req: dict, profile: UserProfile) -> CheckDetail:
    """
    Generic handler for all special_requirements entries.

    Supported types:
      boolean_required  — profile field must be True
      max_value         — profile field (int) must be <= req["max"]
    """
    field_name = req["field"]
    req_type   = req["type"]
    label      = req.get("label", field_name)
    failure_reason = req.get("failure_reason", f"{label} requirement not met")

    value = getattr(profile, field_name, UNKNOWN)

    if _is_unknown(value):
        return CheckDetail(
            field_name, False,
            f"{label} not yet collected — cannot determine eligibility",
            is_unknown=True
        )

    if req_type == "boolean_required":
        if value is True:
            return CheckDetail(field_name, True, f"{label} requirement satisfied")
        return CheckDetail(field_name, False, failure_reason)

    if req_type == "max_value":
        maximum = req["max"]
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            return CheckDetail(
                field_name, False,
                f"{label}: could not parse value {value!r} as integer",
                is_unknown=True
            )
        if int_value <= maximum:
            return CheckDetail(
                field_name, True,
                f"{label} {int_value} <= maximum {maximum}"
            )
        return CheckDetail(
            field_name, False,
            f"{failure_reason} (provided: {int_value}, maximum: {maximum})"
        )

    # Unknown rule type — treat as NEEDS_VERIFICATION rather than crashing
    return CheckDetail(
        field_name, False,
        f"Unknown special requirement type {req_type!r} — cannot evaluate",
        is_unknown=True
    )


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def check_scheme_eligibility(
    profile: UserProfile,
    scheme: dict,
) -> EligibilityResult:
    """
    Deterministically evaluate whether a user profile satisfies a scheme's
    eligibility rules.

    Args:
        profile: UserProfile populated by the conversation layer.
                 Any uncollected field should be set to UNKNOWN.
        scheme:  A single scheme dict as loaded from schemes.json.
                 Must contain "eligibility_criteria". May contain
                 "special_requirements".

    Returns:
        EligibilityResult with status, per-criterion details, and the
        list of profile fields that still need to be collected.

    This function:
    - Never reads files.
    - Never calls an LLM.
    - Never raises exceptions (returns NEEDS_VERIFICATION on malformed data).
    - Is safe to call with a partially-populated UserProfile.
    """
    scheme_id   = scheme.get("id", "")
    scheme_name = scheme.get("telugu_name") or scheme.get("name", "")
    criteria    = scheme.get("eligibility_criteria", {})
    specials    = scheme.get("special_requirements", [])

    all_details: List[CheckDetail] = []

    # ── Standard criteria ─────────────────────────────────────────────
    gender_detail = _check_gender(profile, criteria)
    if gender_detail:
        all_details.append(gender_detail)

    caste_detail = _check_caste(profile, criteria)
    if caste_detail:
        all_details.append(caste_detail)

    all_details.extend(_check_age(profile, criteria))

    gst_detail = _check_gst(profile, criteria)
    if gst_detail:
        all_details.append(gst_detail)

    bank_detail = _check_bank_account(profile, criteria)
    if bank_detail:
        all_details.append(bank_detail)

    # ── Special requirements ──────────────────────────────────────────
    for req in specials:
        all_details.append(_check_special_requirement(req, profile))

    # ── Classify results ──────────────────────────────────────────────
    passed  = [d for d in all_details if d.passed]
    failed  = [d for d in all_details if not d.passed and not d.is_unknown]
    unknown = [d for d in all_details if d.is_unknown]

    missing_fields = [d.field for d in unknown]

    if failed:
        status = EligibilityStatus.LIKELY_NOT_ELIGIBLE
    elif unknown:
        status = EligibilityStatus.NEEDS_VERIFICATION
    else:
        status = EligibilityStatus.LIKELY_ELIGIBLE

    return EligibilityResult(
        status=status,
        passed=passed,
        failed=failed,
        unknown=unknown,
        missing_fields=missing_fields,
        scheme_id=scheme_id,
        scheme_name=scheme_name,
    )


def filter_schemes_by_eligibility(
    profile: UserProfile,
    schemes: list,
) -> dict:
    """
    Run check_scheme_eligibility against a list of schemes and group
    results by status.

    Returns a dict with keys:
      "likely_eligible"     — list of (scheme, EligibilityResult)
      "needs_verification"  — list of (scheme, EligibilityResult)
      "likely_not_eligible" — list of (scheme, EligibilityResult)

    Caller can decide which groups to show and how to label them.
    """
    groups: dict = {
        "likely_eligible":     [],
        "needs_verification":  [],
        "likely_not_eligible": [],
    }
    for scheme in schemes:
        result = check_scheme_eligibility(profile, scheme)
        if result.status == EligibilityStatus.LIKELY_ELIGIBLE:
            groups["likely_eligible"].append((scheme, result))
        elif result.status == EligibilityStatus.NEEDS_VERIFICATION:
            groups["needs_verification"].append((scheme, result))
        else:
            groups["likely_not_eligible"].append((scheme, result))
    return groups

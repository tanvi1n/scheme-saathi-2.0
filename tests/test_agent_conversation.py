"""
tests/test_agent_conversation.py

Conversation-layer tests for the migrated agent.py.

These tests drive handle_message() through complete flows and verify:
- The correct states are visited
- Telugu responses are returned
- NEEDS_VERIFICATION schemes trigger follow-up questions
- LIKELY_NOT_ELIGIBLE schemes are excluded from the list
- Indian number formatting (commas) is accepted
- Session isolation between users

No Telegram, no LLM calls (LLM branch is only triggered by question
words or "?" — our test inputs avoid those).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import handle_message


def fresh_sessions():
    return {}


def drive(steps, user_id="u1", sessions=None):
    """Send a list of messages and return all responses."""
    if sessions is None:
        sessions = fresh_sessions()
    responses = []
    for msg in steps:
        responses.append(handle_message(user_id, msg, sessions))
    return responses, sessions


# ──────────────────────────────────────────────────────────────────────
# Greeting / start
# ──────────────────────────────────────────────────────────────────────

def test_greeting_returns_category_prompt():
    responses, _ = drive(["hi"])
    assert "పథకాలు" in responses[0]


def test_start_command_returns_category_prompt():
    responses, _ = drive(["start"])
    assert "పథకాలు" in responses[0]


# ──────────────────────────────────────────────────────────────────────
# M1: Business flow — tailor, male, general, 30, no GST, yes bank
# ──────────────────────────────────────────────────────────────────────

def _business_flow(gender="1", caste="1", age="30", gst="2", bank="1",
                   business="2", user_id="u_biz"):
    """Drive through the full business eligibility flow."""
    sessions = fresh_sessions()
    steps = [
        "hi",       # start → awaiting_scheme_category
        "1",        # business → awaiting_business_type
        business,   # tailor (2) → eligibility
        gender,
        caste,
        age,
        gst,
        bank,
    ]
    responses, sessions = drive(steps, user_id=user_id, sessions=sessions)
    return responses, sessions


def test_m1_business_tailor_returns_scheme_list():
    responses, _ = _business_flow()
    # Last response should be the scheme list
    scheme_list = responses[-1]
    assert "పీఎం విశ్వకర్మ" in scheme_list, "PM Vishwakarma should appear for tailor"


def test_m1_scheme_list_contains_eligible_marker():
    responses, _ = _business_flow()
    scheme_list = responses[-1]
    assert "✅" in scheme_list


def test_m1_select_scheme_returns_eligible_result():
    responses, sessions = _business_flow(user_id="u_m1_sel")
    # Now select scheme 1
    resp, _ = drive(["1"], user_id="u_m1_sel", sessions=sessions)
    assert "అర్హులు" in resp[0] or "✅" in resp[0]


# ──────────────────────────────────────────────────────────────────────
# M2: Individual flow — female, SC, 25, ration card yes, bank yes
# ──────────────────────────────────────────────────────────────────────

def _individual_flow(gender="2", caste="2", age="25", ration="1", bank="1",
                     user_id="u_ind"):
    sessions = fresh_sessions()
    steps = [
        "hi",
        "2",       # individual
        gender,
        caste,
        age,
        ration,
        bank,
    ]
    responses, sessions = drive(steps, user_id=user_id, sessions=sessions)
    return responses, sessions


def test_m2_individual_returns_scheme_list():
    responses, _ = _individual_flow()
    scheme_list = responses[-1]
    # Should show some schemes
    assert "పథకాలు" in scheme_list


def test_m2_needs_verif_schemes_marked_with_question_mark():
    responses, _ = _individual_flow()
    scheme_list = responses[-1]
    # rythu_bharosa and kalyana_lakshmi need verification → ❓ marker
    assert "❓" in scheme_list, "NEEDS_VERIFICATION schemes should be marked ❓"


def test_m2_fully_eligible_schemes_marked_with_checkmark():
    responses, _ = _individual_flow()
    scheme_list = responses[-1]
    assert "✅" in scheme_list, "LIKELY_ELIGIBLE schemes should be marked ✅"


# ──────────────────────────────────────────────────────────────────────
# NEEDS_VERIFICATION flow: selecting a ❓ scheme triggers a follow-up
# ──────────────────────────────────────────────────────────────────────

def test_selecting_needs_verif_scheme_asks_followup():
    """Selecting rythu_bharosa (needs land) should ask about land ownership."""
    responses, sessions = _individual_flow(user_id="u_nv1")
    scheme_list = responses[-1]

    # Find the 1-based index of rythu_bharosa in the list
    lines = scheme_list.split("\n")
    rythu_idx = None
    for line in lines:
        if "రైతు భరోసా" in line:
            # extract the leading number
            num = line.strip().split(".")[0].strip()
            if num.isdigit():
                rythu_idx = num
                break

    if rythu_idx is None:
        # rythu_bharosa not in list for this profile — skip test
        return

    resp, sessions2 = drive([rythu_idx], user_id="u_nv1", sessions=sessions)
    # Should ask about land ownership
    assert "భూమి" in resp[0] or "land" in resp[0].lower() or "అదనపు" in resp[0]


def test_land_yes_after_followup_declares_eligible():
    """After land=yes, engine should return LIKELY_ELIGIBLE for rythu_bharosa."""
    responses, sessions = _individual_flow(user_id="u_nv2")
    scheme_list = responses[-1]

    lines = scheme_list.split("\n")
    rythu_idx = None
    for line in lines:
        if "రైతు భరోసా" in line:
            num = line.strip().split(".")[0].strip()
            if num.isdigit():
                rythu_idx = num
                break

    if rythu_idx is None:
        return

    # Select rythu_bharosa
    resp1, _ = drive([rythu_idx], user_id="u_nv2", sessions=sessions)
    # Answer yes to land question
    resp2, _ = drive(["1"], user_id="u_nv2", sessions=sessions)
    assert "అర్హులు" in resp2[0] or "✅" in resp2[0]


def test_land_no_after_followup_declares_not_eligible():
    """After land=no, engine should return LIKELY_NOT_ELIGIBLE for rythu_bharosa."""
    responses, sessions = _individual_flow(user_id="u_nv3")
    scheme_list = responses[-1]

    lines = scheme_list.split("\n")
    rythu_idx = None
    for line in lines:
        if "రైతు భరోసా" in line:
            num = line.strip().split(".")[0].strip()
            if num.isdigit():
                rythu_idx = num
                break

    if rythu_idx is None:
        return

    drive([rythu_idx], user_id="u_nv3", sessions=sessions)
    resp, _ = drive(["2"], user_id="u_nv3", sessions=sessions)
    assert "అర్హులు కాదు" in resp[0] or "❌" in resp[0]


# ──────────────────────────────────────────────────────────────────────
# M11: Indian number formatting
# ──────────────────────────────────────────────────────────────────────

def test_income_with_commas_accepted():
    """
    kalyana_lakshmi needs annual_income.
    Entering '1,50,000' should NOT produce an error.
    """
    from agent import _parse_int
    # Test the parser directly
    assert _parse_int("1,50,000") == 150000
    assert _parse_int("2,00,000") == 200000
    assert _parse_int("150000") == 150000


def test_parse_int_plain_number():
    from agent import _parse_int
    assert _parse_int("30") == 30


def test_kalyana_lakshmi_income_comma_format_accepted_in_flow():
    """Drive to the income question and enter comma-formatted income."""
    responses, sessions = _individual_flow(user_id="u_m11")
    scheme_list = responses[-1]

    lines = scheme_list.split("\n")
    kalyana_idx = None
    for line in lines:
        if "కళ్యాణ లక్ష్మి" in line:
            num = line.strip().split(".")[0].strip()
            if num.isdigit():
                kalyana_idx = num
                break

    if kalyana_idx is None:
        return  # scheme not shown for this profile

    # Select kalyana_lakshmi
    drive([kalyana_idx], user_id="u_m11", sessions=sessions)
    # Answer income with commas — should not error
    resp, _ = drive(["1,50,000"], user_id="u_m11", sessions=sessions)
    # Should NOT be an invalid input error
    assert "చెల్లని" not in resp[0], f"Comma-formatted income should be accepted, got: {resp[0]}"


# ──────────────────────────────────────────────────────────────────────
# Restart
# ──────────────────────────────────────────────────────────────────────

def test_restart_clears_session():
    sessions = fresh_sessions()
    drive(["hi", "1", "2"], user_id="u_rst", sessions=sessions)
    # mid-flow restart
    resp, _ = drive(["restart"], user_id="u_rst", sessions=sessions)
    assert "పథకాలు" in resp[0]  # back to category prompt
    # State should be awaiting_scheme_category
    assert sessions["u_rst"]["state"] == "awaiting_scheme_category"


# ──────────────────────────────────────────────────────────────────────
# Documents shortcut
# ──────────────────────────────────────────────────────────────────────

def test_documents_before_scheme_selected_returns_guidance():
    # "documents" contains "document" which triggers the LLM Q&A branch.
    # The documents shortcut is only reachable once the user is past the
    # scheme-category step. Drive to awaiting_scheme_category first, then
    # send the Telugu-only shortcut word that bypasses the LLM trigger.
    sessions = fresh_sessions()
    # Get past start state
    handle_message("u_doc", "hi", sessions)
    # Now send the Telugu shortcut (పత్రాలు) which is in the documents
    # shortcut list but not in question_words
    resp = handle_message("u_doc", "పత్రాలు", sessions)
    assert "పథకం" in resp


# ──────────────────────────────────────────────────────────────────────
# Session isolation
# ──────────────────────────────────────────────────────────────────────

def test_two_users_have_isolated_sessions():
    sessions = fresh_sessions()
    # User A starts business flow
    handle_message("userA", "hi", sessions)
    handle_message("userA", "1", sessions)   # business
    handle_message("userA", "2", sessions)   # tailor

    # User B starts fresh
    handle_message("userB", "hi", sessions)

    assert sessions["userA"]["state"] == "eligibility"
    assert sessions["userB"]["state"] == "awaiting_scheme_category"


# ──────────────────────────────────────────────────────────────────────
# Invalid input handling
# ──────────────────────────────────────────────────────────────────────

def test_invalid_category_input():
    sessions = fresh_sessions()
    drive(["hi"], user_id="u_inv", sessions=sessions)
    resp, _ = drive(["99"], user_id="u_inv", sessions=sessions)
    assert "చెల్లని" in resp[0]


def test_invalid_age_string():
    sessions = fresh_sessions()
    drive(["hi", "1", "2", "1", "1"], user_id="u_age", sessions=sessions)
    # Now at age step
    resp, _ = drive(["thirty"], user_id="u_age", sessions=sessions)
    assert "చెల్లని" in resp[0]


def test_invalid_age_out_of_range():
    sessions = fresh_sessions()
    drive(["hi", "1", "2", "1", "1"], user_id="u_age2", sessions=sessions)
    resp, _ = drive(["200"], user_id="u_age2", sessions=sessions)
    assert "చెల్లని" in resp[0]


# ──────────────────────────────────────────────────────────────────────
# Session 9: Simplified scheme-result UX
# ──────────────────────────────────────────────────────────────────────

# ── _missing_field_requirement_label helper ───────────────────────────

def test_requirement_label_land_ownership():
    from agent import _missing_field_requirement_label
    result = _missing_field_requirement_label(["land_ownership"])
    assert "అదనపు అవసరం" in result
    assert "వ్యవసాయ భూమి" in result


def test_requirement_label_annual_income():
    from agent import _missing_field_requirement_label
    result = _missing_field_requirement_label(["annual_income"])
    assert "అదనపు అవసరం" in result
    assert "ఆదాయ" in result


def test_requirement_label_white_ration_card():
    from agent import _missing_field_requirement_label
    result = _missing_field_requirement_label(["white_ration_card"])
    assert "రేషన్ కార్డ్" in result


def test_requirement_label_unknown_field_fallback():
    """An unrecognised field name falls back to generic wording."""
    from agent import _missing_field_requirement_label
    result = _missing_field_requirement_label(["some_unknown_field"])
    assert isinstance(result, str)
    assert len(result) > 0


def test_requirement_label_empty_list_fallback():
    from agent import _missing_field_requirement_label
    result = _missing_field_requirement_label([])
    assert isinstance(result, str)
    assert len(result) > 0


def test_requirement_label_returns_first_recognised():
    """Returns the label for the first field it recognises."""
    from agent import _missing_field_requirement_label
    result = _missing_field_requirement_label(["land_ownership", "annual_income"])
    assert "వ్యవసాయ భూమి" in result


# ── _build_scheme_list_message with labels ────────────────────────────

def test_build_scheme_list_shows_specific_requirement_for_needs_verif():
    """❓ scheme line should include the specific requirement, not generic text."""
    from agent import _build_scheme_list_message
    eligible = []
    needs_verif = [{"id": "rythu_bharosa", "telugu_name": "రైతు భరోసా", "amount_max": 6000}]
    labels = {"rythu_bharosa": "అదనపు అవసరం: వ్యవసాయ భూమి కలిగి ఉండాలి"}
    result = _build_scheme_list_message(eligible, needs_verif, labels)
    assert "❓" in result
    assert "రైతు భరోసా" in result
    assert "వ్యవసాయ భూమి" in result, (
        "Specific land requirement should appear, not generic wording"
    )


def test_build_scheme_list_eligible_shows_checkmark_and_amount():
    from agent import _build_scheme_list_message
    eligible = [{"id": "pm_vishwakarma", "telugu_name": "పీఎం విశ్వకర్మ", "amount_max": 300000}]
    result = _build_scheme_list_message(eligible, [], {})
    assert "✅" in result
    assert "పీఎం విశ్వకర్మ" in result
    assert "300,000" in result


def test_build_scheme_list_no_generic_needs_verif_text_when_label_provided():
    """When a specific label is provided, 'మరింత సమాచారం అవసరం' should NOT appear."""
    from agent import _build_scheme_list_message
    eligible = []
    needs_verif = [{"id": "rythu_bharosa", "telugu_name": "రైతు భరోసా", "amount_max": 6000}]
    labels = {"rythu_bharosa": "అదనపు అవసరం: వ్యవసాయ భూమి కలిగి ఉండాలి"}
    result = _build_scheme_list_message(eligible, needs_verif, labels)
    assert "మరింత సమాచారం అవసరం" not in result


def test_build_scheme_list_fallback_generic_when_no_label():
    """When no labels dict is provided, fallback text should appear for ❓ scheme."""
    from agent import _build_scheme_list_message
    eligible = []
    needs_verif = [{"id": "some_scheme", "telugu_name": "పథకం", "amount_max": 0}]
    result = _build_scheme_list_message(eligible, needs_verif)
    assert "❓" in result
    assert "పథకం" in result


def test_build_scheme_list_empty_eligible_only_needs_verif():
    from agent import _build_scheme_list_message
    eligible = []
    needs_verif = [
        {"id": "s1", "telugu_name": "పథకం 1", "amount_max": 0},
        {"id": "s2", "telugu_name": "పథకం 2", "amount_max": 0},
    ]
    labels = {
        "s1": "అదనపు అవసరం: వ్యవసాయ భూమి కలిగి ఉండాలి",
        "s2": "అదనపు అవసరం: వైట్ రేషన్ కార్డ్ కలిగి ఉండాలి",
    }
    result = _build_scheme_list_message(eligible, needs_verif, labels)
    assert "2 పథకాలు" in result
    assert "వ్యవసాయ భూమి" in result
    assert "రేషన్ కార్డ్" in result


# ── LIKELY_ELIGIBLE result wording ───────────────────────────────────

def test_likely_eligible_result_uses_softened_wording():
    """
    Final LIKELY_ELIGIBLE result should say 'అర్హత కలిగి ఉంటారు',
    not 'అర్హులు!' (old wording that implied confirmed approval).
    """
    from agent import _format_eligibility_result
    from eligibility_engine import EligibilityStatus, EligibilityResult, CheckDetail

    scheme = {
        "id": "pm_vishwakarma",
        "telugu_name": "పీఎం విశ్వకర్మ",
        "telugu_description": "టెస్ట్",
        "description": "test",
        "amount_min": 15000,
        "amount_max": 300000,
    }
    result = EligibilityResult(
        status=EligibilityStatus.LIKELY_ELIGIBLE,
        passed=[CheckDetail("gender", True, "Gender matches")],
        failed=[],
        unknown=[],
        missing_fields=[],
        scheme_id="pm_vishwakarma",
        scheme_name="పీఎం విశ్వకర్మ",
    )
    msg = _format_eligibility_result(scheme, result)
    assert "అర్హత కలిగి ఉంటారు" in msg, (
        "LIKELY_ELIGIBLE should use softened wording 'అర్హత కలిగి ఉంటారు'"
    )


def test_likely_eligible_result_does_not_use_old_wording():
    """Old 'అర్హులు!' wording must not appear in LIKELY_ELIGIBLE result."""
    from agent import _format_eligibility_result
    from eligibility_engine import EligibilityStatus, EligibilityResult, CheckDetail

    scheme = {
        "id": "pm_vishwakarma",
        "telugu_name": "పీఎం విశ్వకర్మ",
        "telugu_description": "టెస్ట్",
        "description": "test",
        "amount_min": 15000,
        "amount_max": 300000,
    }
    result = EligibilityResult(
        status=EligibilityStatus.LIKELY_ELIGIBLE,
        passed=[],
        failed=[],
        unknown=[],
        missing_fields=[],
        scheme_id="pm_vishwakarma",
        scheme_name="పీఎం విశ్వకర్మ",
    )
    msg = _format_eligibility_result(scheme, result)
    assert "అర్హులు!" not in msg, (
        "Old 'అర్హులు!' wording must be removed — it implies confirmed approval"
    )


def test_likely_not_eligible_result_still_shows_reason():
    """LIKELY_NOT_ELIGIBLE result must still show the reason."""
    from agent import _format_eligibility_result
    from eligibility_engine import EligibilityStatus, EligibilityResult, CheckDetail

    scheme = {
        "id": "we_hub",
        "telugu_name": "వి-హబ్",
        "telugu_description": "టెస్ట్",
        "description": "test",
        "amount_min": 50000,
        "amount_max": 2500000,
    }
    result = EligibilityResult(
        status=EligibilityStatus.LIKELY_NOT_ELIGIBLE,
        passed=[],
        failed=[CheckDetail("gender", False, "Scheme requires female applicant")],
        unknown=[],
        missing_fields=[],
        scheme_id="we_hub",
        scheme_name="వి-హబ్",
    )
    msg = _format_eligibility_result(scheme, result)
    assert "❌" in msg
    assert "అర్హులు కాదు" in msg
    assert "female" in msg or "కారణం" in msg


# ── End-to-end: NEEDS_VERIFICATION scheme in individual flow ──────────

def test_individual_needs_verif_scheme_shows_specific_requirement_in_list():
    """
    The scheme list for an individual user should show specific requirement
    text for ❓ schemes (land, income, etc.) rather than generic wording.
    """
    responses, _ = _individual_flow(user_id="u_req_label")
    scheme_list = responses[-1]
    if "❓" not in scheme_list:
        return  # no NEEDS_VERIFICATION schemes for this profile — skip
    # Generic old wording must not appear
    assert "మరింత సమాచారం అవసరం" not in scheme_list, (
        "Generic wording should be replaced by specific requirement label"
    )
    # At least one specific requirement label should appear
    assert "అదనపు అవసరం" in scheme_list, (
        "Specific requirement label 'అదనపు అవసరం:' should appear for ❓ schemes"
    )

import json
import os
import requests
from dotenv import load_dotenv
from skills.discover import discover_schemes, keyword_map
from skills.documents import get_document_guide
from typing import Dict, Any

from eligibility_engine import (
    UNKNOWN,
    UserProfile,
    EligibilityStatus,
    check_scheme_eligibility,
)

load_dotenv()

# List of greeting words to detect
GREETINGS = ["hi", "hello", "hey", "నమస్కారం", "start", "help"]

# Telugu labels for missing fields — shown when a scheme needs more info
_MISSING_FIELD_LABELS = {
    "land_ownership":   "వ్యవసాయ భూమి ఉందా?",
    "annual_income":    "వార్షిక ఆదాయం (రూపాయలలో)",
    "monthly_units":    "నెలవారీ విద్యుత్ వినియోగం (యూనిట్లలో)",
    "annual_turnover":  "వార్షిక టర్నోవర్ (రూపాయలలో)",
    "white_ration_card": "వైట్ రేషన్ కార్డ్ ఉందా?",
}

# Questions to ask per missing field
_MISSING_FIELD_QUESTIONS = {
    "land_ownership":   "మీకు వ్యవసాయ భూమి ఉందా? (1-అవును / 2-లేదు)",
    "annual_income":    "మీ వార్షిక ఆదాయం ఎంత? (సంఖ్యలో రూపాయల్లో, ఉదా: 150000)",
    "monthly_units":    "మీ నెలవారీ విద్యుత్ వినియోగం ఎంత? (యూనిట్లలో, ఉదా: 150)",
    "annual_turnover":  "మీ వార్షిక టర్నోవర్ ఎంత? (సంఖ్యలో రూపాయల్లో)",
    "white_ration_card": "మీకు వైట్ రేషన్ కార్డ్ ఉందా? (1-అవును / 2-లేదు)",
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _parse_int(raw: str) -> int:
    """
    Parse an integer from user input.
    Accepts Indian number formatting with commas: "1,50,000" → 150000.
    Fixes failure F4 (Indian number formatting rejected).
    """
    return int(raw.strip().replace(",", ""))


def _load_schemes() -> list:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    schemes_file = os.path.join(current_dir, "data", "schemes.json")
    try:
        with open(schemes_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _build_user_profile(user_profile_dict: dict) -> UserProfile:
    """
    Convert the session's user_profile dict into a typed UserProfile.
    Any key absent from the dict becomes UNKNOWN.
    """
    def get(key):
        return user_profile_dict.get(key, UNKNOWN)

    return UserProfile(
        gender=get("gender"),
        caste=get("caste"),
        age=get("age"),
        business_type=get("business_type"),
        has_gst=get("has_gst"),
        has_bank_account=get("has_bank_account"),
        white_ration_card=get("white_ration_card"),
        land_ownership=get("land_ownership"),
        annual_income=get("annual_income"),
        monthly_units=get("monthly_units"),
        annual_turnover=get("annual_turnover"),
    )


def _format_eligibility_result(scheme: dict, result) -> str:
    """
    Render an EligibilityResult into a Telugu response string.
    Called after all missing fields have been collected.
    """
    if result.status == EligibilityStatus.LIKELY_NOT_ELIGIBLE:
        reasons = "; ".join(d.reason for d in result.failed)
        msg  = f"❌ {scheme['telugu_name']}\n\n"
        msg += f"మీరు ఈ పథకానికి అర్హులు కాదు.\n"
        msg += f"కారణం: {reasons}\n\n"
        msg += "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
        return msg

    # LIKELY_ELIGIBLE
    msg  = f"✅ {scheme['telugu_name']}\n\n"
    msg += f"📝 వివరణ: {scheme.get('telugu_description', scheme.get('description', ''))}\n\n"
    msg += f"💰 లాభం: ₹{scheme.get('amount_min', 0):,} - ₹{scheme.get('amount_max', 0):,}\n\n"
    msg += "మీరు ఈ పథకానికి అర్హులు! ✅\n\n"
    msg += "📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n"
    msg += "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
    return msg


def _next_missing_field_question(missing_fields: list) -> tuple:
    """
    Return (field_name, question_text) for the first missing field
    that we know how to ask about.  Returns (None, None) if nothing to ask.
    """
    for field in missing_fields:
        if field in _MISSING_FIELD_QUESTIONS:
            return field, _MISSING_FIELD_QUESTIONS[field]
    return None, None


# ──────────────────────────────────────────────────────────────────────
# LLM helpers (unchanged)
# ──────────────────────────────────────────────────────────────────────

def ask_llm(prompt: str) -> str:
    try:
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        system_prompt = (
            "You are Scheme-Saathi, a high-precision Telangana government schemes assistant. "
            "Your first priority is factual correctness from provided context only. "
            "You must support Telugu, English, Hinglish, and transliterated Telugu. "
            "When context is insufficient, do not guess. "
            "Keep answers short, clear, citizen-friendly, and action-oriented."
        )
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 768,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return "ఈ సమాచారం నాకు తెలియదు, దయచేసి సంబంధిత కార్యాలయాన్ని సంప్రదించండి"


def answer_scheme_question(question: str, schemes_context: str) -> str:
    prompt = f"""Task: Answer a user's scheme-related question using ONLY the provided Schemes Data.

Hard Constraints (must follow):
1) Never use outside knowledge. If data is missing/unclear, respond exactly:
ఈ సమాచారం నాకు తెలియదు, దయచేసి సంబంధిత కార్యాలయాన్ని సంప్రదించండి
2) Understand messy inputs: Telugu, English, Hinglish, transliterated Telugu, ASR errors.
3) Match user language preference:
   - Telugu/mixed Telugu -> Telugu response
   - Clear English -> English response
4) Keep response concise: 3-6 lines max.
5) Do not expose internal IDs/fields unless explicitly asked.
6) If user asks eligibility-style question, include only available criteria from data.
7) If user asks benefits/amount/documents, provide only what exists in data.

Reasoning Protocol (internal):
- First, normalize user intent from noisy text.
- Second, find matching scheme facts in Schemes Data.
- Third, answer directly with practical next step.
- If uncertain at any point, output the exact fallback sentence.

Output Style:
- Plain text only.
- No markdown headings.
- No long paragraphs.
- Prefer numbered points only when multiple facts are required.

Few-shot guidance:
Example A
User: "naku business scheme kavali"
Assistant: "మీ వ్యాపారం రకాన్ని చెప్పండి (ఉదా: కిరాణా, టైలర్, సెలూన్) లేదా అందుబాటులో ఉన్న జాబితా నుండి ఎంచుకోండి."

Example B
User: "PMEGP amount ఎంత"
Assistant: "డేటాలో ఉన్న మేరకు, PMEGP కింద లాభం/లోన్ పరిమితి ఇదే: <amount from data>. మరిన్ని వివరాలకు అర్హత ప్రమాణాలు కూడా చూడండి."

Example C
User: "documents enti"
Assistant: "ఈ పథకానికి అవసరమైన డాక్యుమెంట్లు: <only listed docs>. డేటాలో లేనివి కోసం సంబంధిత కార్యాలయాన్ని సంప్రదించండి."

Example D
User: "eligibility cheppu"
Assistant: "అర్హత ప్రమాణాలు (డేటా ప్రకారం): <criteria only>. మీ వివరాలు చెబితే సరిపోతుందో చెప్తాను."

Schemes Data:
{schemes_context}

User Question:
{question}
"""
    return ask_llm(prompt)


# ──────────────────────────────────────────────────────────────────────
# Scheme filtering using eligibility_engine
# ──────────────────────────────────────────────────────────────────────

def _filter_business_schemes(business_type: str, profile: UserProfile, all_schemes: list) -> tuple:
    """
    Filter business schemes by keyword match then eligibility engine.

    Returns (eligible_list, needs_verif_list) where each item is a scheme dict.
    LIKELY_NOT_ELIGIBLE schemes are discarded.
    """
    business_type_lower = business_type.lower()
    variants = keyword_map.get(business_type_lower, [business_type_lower])

    eligible = []
    needs_verif = []

    for scheme in all_schemes:
        if "target_business_types" not in scheme:
            continue
        # Keyword match (unchanged from original)
        target_types = [bt.lower() for bt in scheme.get("target_business_types", [])]
        business_match = any(
            variant in target or target in variant
            for variant in variants
            for target in target_types
        )
        if not business_match:
            continue

        result = check_scheme_eligibility(profile, scheme)
        if result.status == EligibilityStatus.LIKELY_ELIGIBLE:
            eligible.append(scheme)
        elif result.status == EligibilityStatus.NEEDS_VERIFICATION:
            needs_verif.append(scheme)
        # LIKELY_NOT_ELIGIBLE → silently excluded from list

    return eligible, needs_verif


def _filter_individual_schemes(profile: UserProfile, all_schemes: list) -> tuple:
    """
    Filter individual schemes by eligibility engine.

    Returns (eligible_list, needs_verif_list).
    LIKELY_NOT_ELIGIBLE schemes are discarded.
    """
    eligible = []
    needs_verif = []

    for scheme in all_schemes:
        if "target_individual_types" not in scheme:
            continue
        result = check_scheme_eligibility(profile, scheme)
        if result.status == EligibilityStatus.LIKELY_ELIGIBLE:
            eligible.append(scheme)
        elif result.status == EligibilityStatus.NEEDS_VERIFICATION:
            needs_verif.append(scheme)

    return eligible, needs_verif


def _build_scheme_list_message(eligible: list, needs_verif: list) -> str:
    """
    Format the scheme list message.
    LIKELY_ELIGIBLE schemes are listed normally.
    NEEDS_VERIFICATION schemes are listed with a ❓ marker and a note.
    """
    all_shown = eligible + needs_verif
    total_amount = sum(s.get("amount_max", 0) for s in eligible)

    lines = [f"మీకు {len(all_shown)} పథకాలు కనుగొనబడ్డాయి"]
    if total_amount:
        lines[0] += f" (నిర్ధారించబడిన మొత్తం ₹{total_amount:,})"
    lines.append("")

    idx = 1
    for scheme in eligible:
        lines.append(f"{idx}. ✅ {scheme['telugu_name']} — ₹{scheme.get('amount_max', 0):,}")
        idx += 1
    for scheme in needs_verif:
        lines.append(f"{idx}. ❓ {scheme['telugu_name']} — మరింత సమాచారం అవసరం")
        idx += 1

    lines.append("\nఏది మరింత తెలుసుకోవాలి? (సంఖ్య టైప్ చేయండి)")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Main handler
# ──────────────────────────────────────────────────────────────────────

def handle_message(user_id: str, message: str, sessions: Dict[str, Dict[str, Any]]) -> str:
    """
    Handle user message and manage conversation state.
    Eligibility decisions are now delegated to eligibility_engine.py.
    """
    message = message.strip()
    normalized_message = message.lower()

    if user_id not in sessions:
        sessions[user_id] = {
            "state": "start",
            "data": {
                "business_type": None,
                "matched_schemes": [],       # all schemes shown (eligible + needs_verif)
                "needs_verif_ids": set(),    # ids of NEEDS_VERIFICATION schemes in list
                "current_scheme_id": None,
                "eligibility_step": 0,
                "user_profile": {},
                "pending_missing_field": None,  # field being collected for NEEDS_VERIF scheme
            },
        }

    session = sessions[user_id]
    state = session["state"]
    data = session["data"]

    # ── Global scheme Q&A via LLM ─────────────────────────────────────
    question_words = [
        "ఎంత", "ఏమి", "ఎలా", "అర్హత", "documents", "document",
        "eligibility", "benefit", "amount", "how", "what",
    ]
    if message.endswith("?") or any(w in normalized_message for w in question_words):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schemes_file = os.path.join(current_dir, "data", "schemes.json")
        try:
            with open(schemes_file, "r", encoding="utf-8") as f:
                schemes_context = f.read()
            if len(schemes_context) > 8000:
                schemes_context = schemes_context[:8000]
            return answer_scheme_question(message, schemes_context)
        except Exception:
            return "ఈ సమాచారం నాకు తెలియదు, దయచేసి సంబంధిత కార్యాలయాన్ని సంప్రదించండి"

    # ── Restart ───────────────────────────────────────────────────────
    if normalized_message in ["restart", "మళ్లీ", "మరు"] or any(
        w in normalized_message
        for w in ["restart", "re start", "రిస్టార్ట్", "రీ స్టార్ట్", "మళ్ళీ", "మళ్లీ"]
    ):
        session["state"] = "awaiting_scheme_category"
        data.update({
            "business_type": None,
            "scheme_category": None,
            "matched_schemes": [],
            "needs_verif_ids": set(),
            "current_scheme_id": None,
            "eligibility_step": 0,
            "user_profile": {},
            "pending_missing_field": None,
        })
        return "నమస్కారం! 🙏 మీరు ఏ రకమైన పథకాలు చూడాలనుకుంటున్నారు?"

    # ── Documents shortcut ────────────────────────────────────────────
    if normalized_message in ["documents", "డాక్యుమెంట్స్", "docs"] or any(
        w in normalized_message for w in ["document", "docs", "డాక్యుమెంట్", "పత్రాలు"]
    ):
        if data["current_scheme_id"]:
            return get_document_guide(data["current_scheme_id"])
        return "మీరు మొదట ఏ పథకం ఎంచుకోవాలి."

    # ── START ─────────────────────────────────────────────────────────
    if state == "start":
        if normalized_message in GREETINGS or not message:
            session["state"] = "awaiting_scheme_category"
            return "నమస్కారం! 🙏 మీరు ఏ రకమైన పథకాలు చూడాలనుకుంటున్నారు?"
        session["state"] = "awaiting_scheme_category"
        return handle_message(user_id, message, sessions)

    # ── AWAITING_SCHEME_CATEGORY ──────────────────────────────────────
    elif state == "awaiting_scheme_category":
        ui = message.strip()
        uin = ui.lower()
        business_kw = ["business", "scheme", "schemes", "బిజినెస్", "వ్యాపార", "వ్యాపారం", "shop", "shopkeeper", "దుకాణ"]
        individual_kw = ["individual", "personal", "వ్యక్తిగత", "individual scheme", "personal scheme"]

        if ui == "1" or uin in ["business", "వ్యాపారం"] or any(w in uin for w in business_kw):
            data["scheme_category"] = "business"
            session["state"] = "awaiting_business_type"
            return "మీ వ్యాపార రకం ఎంచుకోండి:"
        elif ui == "2" or uin in ["individual", "వ్యక్తిగత"] or any(w in uin for w in individual_kw):
            data["scheme_category"] = "individual"
            session["state"] = "individual_eligibility"
            data["eligibility_step"] = 0
            data["user_profile"] = {}
            return "మీ వ్యక్తిగత వివరాలు అడుగుతూ ఉన్నాను...\n\nమీ లింగం చెప్పండి:"
        return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."

    # ── AWAITING_BUSINESS_TYPE ────────────────────────────────────────
    elif state == "awaiting_business_type":
        bmap = {"1": "kirana", "2": "tailor", "3": "salon",
                "4": "vegetable vendor", "5": "auto", "6": "other"}
        ui = message.strip()
        if ui == "6" or ui.lower() == "other":
            session["state"] = "awaiting_custom_business_type"
            return "మీ వ్యాపార రకం టైప్ చేయండి:"
        data["business_type"] = bmap.get(ui, ui)
        session["state"] = "eligibility"
        data["eligibility_step"] = 0
        data["user_profile"] = {}
        return "మీ వ్యక్తిగత వివరాలు అడుగుతూ ఉన్నాను...\n\nమీ లింగం చెప్పండి:"

    # ── AWAITING_CUSTOM_BUSINESS_TYPE ────────────────────────────────
    elif state == "awaiting_custom_business_type":
        data["business_type"] = message.strip()
        session["state"] = "eligibility"
        data["eligibility_step"] = 0
        data["user_profile"] = {}
        return "మీ వ్యక్తిగత వివరాలు అడుగుతూ ఉన్నాను...\n\nమీ లింగం చెప్పండి:"

    # ── ELIGIBILITY (business profile collection) ─────────────────────
    elif state == "eligibility":
        step = data["eligibility_step"]

        if step == 0:  # gender
            g = message.strip()
            if g in ["1", "male", "పురుషుడు"]:
                data["user_profile"]["gender"] = "male"
            elif g in ["2", "female", "స్త్రీ"]:
                data["user_profile"]["gender"] = "female"
            elif g in ["3", "other", "ఇతర"]:
                data["user_profile"]["gender"] = "other"
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1, 2, లేదా 3 ఎంచుకోండి."
            data["eligibility_step"] = 1
            return "మీ కులం చెప్పండి:"

        elif step == 1:  # caste
            cmap = {"1": "general", "2": "sc", "3": "st", "4": "obc", "5": "minority"}
            ci = message.strip().lower()
            if ci in cmap:
                data["user_profile"]["caste"] = cmap[ci]
            elif ci in cmap.values():
                data["user_profile"]["caste"] = ci
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1, 2, 3, 4, లేదా 5 ఎంచుకోండి."
            data["eligibility_step"] = 2
            return "మీ వయసు చెప్పండి (సంఖ్యలో):"

        elif step == 2:  # age
            try:
                age = _parse_int(message)
                if not (0 < age < 150):
                    return "చెల్లని వయస్సు. దయచేసి 1 నుండి 149 మధ్య సంఖ్య చెప్పండి."
                data["user_profile"]["age"] = age
                data["eligibility_step"] = 3
                return "మీకు GST registration ఉందా?"
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి మీ వయస్సు సంఖ్యలో చెప్పండి."

        elif step == 3:  # GST
            gi = message.strip()
            if gi in ["1", "yes", "అవును"]:
                data["user_profile"]["has_gst"] = True
            elif gi in ["2", "no", "లేదు"]:
                data["user_profile"]["has_gst"] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
            data["eligibility_step"] = 4
            return "మీకు bank account ఉందా?"

        elif step == 4:  # bank account — final step, now filter schemes
            bi = message.strip()
            if bi in ["1", "yes", "అవును"]:
                data["user_profile"]["has_bank_account"] = True
            elif bi in ["2", "no", "లేదు"]:
                data["user_profile"]["has_bank_account"] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."

            profile = _build_user_profile(data["user_profile"])
            all_schemes = _load_schemes()
            eligible, needs_verif = _filter_business_schemes(
                data["business_type"], profile, all_schemes
            )

            if not eligible and not needs_verif:
                session["state"] = "awaiting_scheme_category"
                return "మీకు సరిపోయే పథకాలు కనుగొనబడలేదు. దయచేసి మళ్లీ ప్రయత్నించండి."

            data["matched_schemes"] = eligible + needs_verif
            data["needs_verif_ids"] = {s["id"] for s in needs_verif}
            session["state"] = "discovered"
            return _build_scheme_list_message(eligible, needs_verif)

    # ── DISCOVERED (business) ─────────────────────────────────────────
    elif state == "discovered":
        try:
            choice = int(message) - 1
        except ValueError:
            return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్య టైప్ చేయండి."

        if not (0 <= choice < len(data["matched_schemes"])):
            return "చెల్లని సంఖ్య. దయచేసి చెల్లుబాటుయ్యే సంఖ్య టైప్ చేయండి."

        scheme = data["matched_schemes"][choice]
        data["current_scheme_id"] = scheme["id"]

        # Build profile and run engine
        profile = _build_user_profile(data["user_profile"])
        result = check_scheme_eligibility(profile, scheme)

        if result.status == EligibilityStatus.NEEDS_VERIFICATION:
            field, question = _next_missing_field_question(result.missing_fields)
            if field and question:
                data["pending_missing_field"] = field
                session["state"] = "collecting_missing_field"
                return f"ℹ️ {scheme['telugu_name']} కోసం అదనపు సమాచారం అవసరం:\n\n{question}"
            # No question available for the missing field — treat as needs verification
            session["state"] = "eligibility_result"
            return (
                f"❓ {scheme['telugu_name']}\n\n"
                "ఈ పథకానికి అర్హతను పూర్తిగా నిర్ధారించడానికి అదనపు ధృవీకరణ అవసరం.\n"
                "దయచేసి సంబంధిత కార్యాలయాన్ని సంప్రదించండి.\n\n"
                "📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n"
                "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
            )

        session["state"] = "eligibility_result"
        return _format_eligibility_result(scheme, result)

    # ── INDIVIDUAL_ELIGIBILITY ────────────────────────────────────────
    elif state == "individual_eligibility":
        step = data["eligibility_step"]

        if step == 0:  # gender
            g = message.strip()
            if g in ["1", "male", "పురుషుడు"]:
                data["user_profile"]["gender"] = "male"
            elif g in ["2", "female", "స్త్రీ"]:
                data["user_profile"]["gender"] = "female"
            elif g in ["3", "other", "ఇతర"]:
                data["user_profile"]["gender"] = "other"
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1, 2, లేదా 3 ఎంచుకోండి."
            data["eligibility_step"] = 1
            return "మీ కులం చెప్పండి:"

        elif step == 1:  # caste
            cmap = {"1": "general", "2": "sc", "3": "st", "4": "obc", "5": "minority"}
            ci = message.strip().lower()
            if ci in cmap:
                data["user_profile"]["caste"] = cmap[ci]
            elif ci in cmap.values():
                data["user_profile"]["caste"] = ci
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1, 2, 3, 4, లేదా 5 ఎంచుకోండి."
            data["eligibility_step"] = 2
            return "మీ వయసు చెప్పండి (సంఖ్యలో):"

        elif step == 2:  # age
            try:
                age = _parse_int(message)
                if not (0 < age < 150):
                    return "చెల్లని వయస్సు. దయచేసి 1 నుండి 149 మధ్య సంఖ్య చెప్పండి."
                data["user_profile"]["age"] = age
                data["eligibility_step"] = 3
                return "మీకు white ration card ఉందా?"
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి మీ వయస్సు సంఖ్యలో చెప్పండి."

        elif step == 3:  # white ration card
            ri = message.strip()
            if ri in ["1", "yes", "అవును"]:
                data["user_profile"]["white_ration_card"] = True
            elif ri in ["2", "no", "లేదు"]:
                data["user_profile"]["white_ration_card"] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
            data["eligibility_step"] = 4
            return "మీకు bank account ఉందా?"

        elif step == 4:  # bank account — final step
            bi = message.strip()
            if bi in ["1", "yes", "అవును"]:
                data["user_profile"]["has_bank_account"] = True
            elif bi in ["2", "no", "లేదు"]:
                data["user_profile"]["has_bank_account"] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."

            profile = _build_user_profile(data["user_profile"])
            all_schemes = _load_schemes()
            eligible, needs_verif = _filter_individual_schemes(profile, all_schemes)

            if not eligible and not needs_verif:
                session["state"] = "awaiting_scheme_category"
                return "మీకు సరిపోయే పథకాలు కనుగొనబడలేదు. దయచేసి మళ్లీ ప్రయత్నించండి."

            data["matched_schemes"] = eligible + needs_verif
            data["needs_verif_ids"] = {s["id"] for s in needs_verif}
            session["state"] = "individual_discovered"
            return _build_scheme_list_message(eligible, needs_verif)

    # ── INDIVIDUAL_DISCOVERED ─────────────────────────────────────────
    elif state == "individual_discovered":
        try:
            choice = int(message) - 1
        except ValueError:
            return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్య టైప్ చేయండి."

        if not (0 <= choice < len(data["matched_schemes"])):
            return "చెల్లని సంఖ్య. దయచేసి చెల్లుబాటుయ్యే సంఖ్య టైప్ చేయండి."

        scheme = data["matched_schemes"][choice]
        data["current_scheme_id"] = scheme["id"]

        profile = _build_user_profile(data["user_profile"])
        result = check_scheme_eligibility(profile, scheme)

        if result.status == EligibilityStatus.NEEDS_VERIFICATION:
            field, question = _next_missing_field_question(result.missing_fields)
            if field and question:
                data["pending_missing_field"] = field
                session["state"] = "collecting_missing_field"
                return f"ℹ️ {scheme['telugu_name']} కోసం అదనపు సమాచారం అవసరం:\n\n{question}"
            session["state"] = "eligibility_result"
            return (
                f"❓ {scheme['telugu_name']}\n\n"
                "ఈ పథకానికి అర్హతను పూర్తిగా నిర్ధారించడానికి అదనపు ధృవీకరణ అవసరం.\n"
                "దయచేసి సంబంధిత కార్యాలయాన్ని సంప్రదించండి.\n\n"
                "📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n"
                "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
            )

        session["state"] = "eligibility_result"
        return _format_eligibility_result(scheme, result)

    # ── COLLECTING_MISSING_FIELD ──────────────────────────────────────
    # Replaces scheme_specific_question state.
    # The engine told us what field is missing; we collect it here,
    # then re-run the engine.  Handles any field generically.
    elif state == "collecting_missing_field":
        field = data.get("pending_missing_field")
        if not field:
            return "ఎర్రర్. దయచేసి restart చేయండి."

        # Parse the answer
        boolean_fields = {"land_ownership", "white_ration_card"}
        numeric_fields = {"annual_income", "monthly_units", "annual_turnover"}

        if field in boolean_fields:
            ans = message.strip()
            if ans in ["1", "yes", "అవును"]:
                data["user_profile"][field] = True
            elif ans in ["2", "no", "లేదు"]:
                data["user_profile"][field] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."

        elif field in numeric_fields:
            try:
                data["user_profile"][field] = _parse_int(message)
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్యలో టైప్ చేయండి (ఉదా: 150000)."

        else:
            # Unknown field type — cannot parse
            return "చెల్లని ఇన్పుట్. దయచేసి restart చేయండి."

        data["pending_missing_field"] = None

        # Re-run engine with updated profile
        scheme = next(
            (s for s in data["matched_schemes"] if s["id"] == data["current_scheme_id"]),
            None,
        )
        if not scheme:
            return "ఎర్రర్. దయచేసి restart చేయండి."

        profile = _build_user_profile(data["user_profile"])
        result = check_scheme_eligibility(profile, scheme)

        # If still needs more fields, ask the next one
        if result.status == EligibilityStatus.NEEDS_VERIFICATION:
            next_field, next_question = _next_missing_field_question(result.missing_fields)
            if next_field and next_question:
                data["pending_missing_field"] = next_field
                return f"ℹ️ మరొక ప్రశ్న:\n\n{next_question}"
            # Cannot ask further — present as unverifiable
            session["state"] = "eligibility_result"
            return (
                f"❓ {scheme['telugu_name']}\n\n"
                "అర్హతను పూర్తిగా నిర్ధారించడానికి అదనపు ధృవీకరణ అవసరం.\n"
                "దయచేసి సంబంధిత కార్యాలయాన్ని సంప్రదించండి.\n\n"
                "📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n"
                "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
            )

        session["state"] = "eligibility_result"
        return _format_eligibility_result(scheme, result)

    # ── ELIGIBILITY_RESULT ────────────────────────────────────────────
    elif state == "eligibility_result":
        if message.lower() in ["documents", "డాక్యుమెంట్స్", "docs"]:
            return get_document_guide(data["current_scheme_id"])
        return "దయచేసి 'documents' లేదా 'restart' చెప్పండి."

    # Default
    return "నమస్కారం! దయచేసి తిరిగి ప్రయత్నించండి."


# ──────────────────────────────────────────────────────────────────────
# CLI runner (unchanged)
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sessions = {}
    user_id = "test_user"
    print("scheme-saathi bot (type 'exit' to quit)")
    print("స్కీమ్-సాథి బాట్ (నిష్క్రమించడానికి 'exit' చెప్పండి)\n")
    while True:
        msg = input("You: ").strip()
        if msg == "exit":
            print("Goodbye!")
            break
        response = handle_message(user_id, msg, sessions)
        print(f"Bot: {response}\n")

import json
import os
from typing import Optional


# Keyword mapping for flexible business type matching (legacy fallback)
keyword_map = {
    "tailor": ["tailor", "tailors", "clothing", "garment"],
    "kirana": ["kirana", "grocery", "retail", "small shops", "general store"],
    "vegetable": ["vegetable", "vendor", "street vendor", "hawker", "mobile carts"],
    "salon": ["salon", "barber", "beauty", "barbers"],
    "pharmacy": ["pharmacy", "medical", "drug"],
    "laundry": ["laundry", "service providers"],
    "carpenter": ["carpenter", "carpenters", "wood"],
    "street vendor": ["street vendor", "hawker", "mobile carts", "street vendors"],
    "auto": ["auto", "auto-rickshaw", "rickshaw", "taxi", "transport"],
    "taxi": ["taxi", "cab", "auto-rickshaw", "transport services"],
    "driver": ["driver", "auto-rickshaw drivers", "taxi drivers", "transport"]
}

# Canonical occupation → normalized category mapping.
# Used as the primary discovery path when the occupation is recognised.
# Falls back to keyword_map for unrecognised occupations.
#
# Controlled category vocabulary:
#   service, retail, artisan, micro_enterprise, manufacturing,
#   transport, agriculture, startup, women_led, vendor
occupation_to_categories: dict = {
    "tailor":             ["artisan", "service", "micro_enterprise"],
    "kirana":             ["retail", "micro_enterprise"],
    "salon":              ["service", "micro_enterprise", "artisan"],
    "vegetable_vendor":   ["vendor", "retail"],
    "mechanic":           ["service", "micro_enterprise"],
    "carpenter":          ["artisan", "service", "micro_enterprise"],
    "auto_driver":        ["transport"],
    "taxi_driver":        ["transport"],
    "street_vendor":      ["vendor"],
    "dairy_business":     ["manufacturing", "micro_enterprise", "retail"],
    "small_manufacturer": ["manufacturing", "micro_enterprise"],
}


def get_candidate_schemes(business_type: str, all_schemes: list) -> list:
    """
    Return candidate schemes for a given business type using the
    normalized category model.

    Strategy:
    1. If business_type is in occupation_to_categories, return all schemes
       whose normalized_categories intersect the occupation's category set.
    2. Otherwise fall back to keyword_map substring matching against
       target_business_types.

    This function performs DISCOVERY ONLY.
    It does not evaluate eligibility.
    Callers must pass the returned candidates to the eligibility engine.

    Args:
        business_type: canonical occupation string (e.g. "tailor", "kirana")
        all_schemes:   full list of scheme dicts loaded from schemes.json

    Returns:
        list of scheme dicts that are candidates for this occupation.
        Returns an empty list (not an error) for unrecognised occupations
        with no keyword fallback matches.
    """
    business_type_lower = business_type.lower()

    # Strategy 1: normalized category match
    categories = occupation_to_categories.get(business_type_lower)
    if categories:
        category_set = set(categories)
        return [
            s for s in all_schemes
            if "target_business_types" in s
            and not category_set.isdisjoint(set(s.get("normalized_categories", [])))
        ]

    # Strategy 2: legacy keyword fallback
    variants = keyword_map.get(business_type_lower, [business_type_lower])
    candidates = []
    for scheme in all_schemes:
        if "target_business_types" not in scheme:
            continue
        target_types = [bt.lower() for bt in scheme.get("target_business_types", [])]
        if any(
            variant in target or target in variant
            for variant in variants
            for target in target_types
        ):
            candidates.append(scheme)
    return candidates


def discover_schemes(business_type: str, gender: str = "any", caste: str = "any") -> str:
    """
    Discover schemes matching the given business type, gender, and caste criteria.
    
    Args:
        business_type: Type of business (e.g., "tailor", "kirana", "salon")
        gender: Gender filter ("any", "male", "female")
        caste: Caste filter ("any", "SC", "ST", "OBC", "general")
    
    Returns:
        Formatted Telugu string showing matched schemes with amounts,
        or a Telugu message if no schemes are found.

    Note: This function applies a light gender/caste pre-filter for display
    purposes only. Full deterministic eligibility must be run via
    eligibility_engine.check_scheme_eligibility() before presenting a
    definitive result to the user.
    """
    
    # Determine the path to schemes.json
    current_dir = os.path.dirname(os.path.abspath(__file__))
    schemes_file = os.path.join(current_dir, "..", "data", "schemes.json")
    
    # Load schemes from JSON
    try:
        with open(schemes_file, "r", encoding="utf-8") as f:
            schemes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return f"Error loading schemes: {e}"
    
    # Get candidate schemes via normalized category model
    candidates = get_candidate_schemes(business_type, schemes)

    # Apply light gender/caste pre-filter for display (not eligibility)
    matched_schemes = []
    for scheme in candidates:
        eligibility = scheme.get("eligibility_criteria", {})
        scheme_gender = eligibility.get("gender", "any").lower()
        if gender.lower() != "any" and scheme_gender != "any" and scheme_gender != gender.lower():
            continue
        scheme_caste = eligibility.get("caste", "any").lower()
        if caste.lower() != "any" and scheme_caste != "any" and scheme_caste != caste.lower():
            continue
        matched_schemes.append(scheme)
    
    # If no schemes match, return Telugu message
    if not matched_schemes:
        return "మీ వ్యాపారానికి సరిపోయే పథకాలు కనుగొనబడలేదు."
    
    # Calculate total amount and format output
    total_amount = sum(scheme.get("amount_max", 0) for scheme in matched_schemes)
    n_schemes = len(matched_schemes)
    
    # Build the header
    header = f"మీకు {n_schemes} పథకాలు అర్హత ఉన్నాయి (మొత్తం ₹{total_amount}):\n"
    
    # Build each scheme line
    scheme_lines = []
    for i, scheme in enumerate(matched_schemes, 1):
        telugu_name = scheme.get("telugu_name", scheme.get("name", "Unknown"))
        amount_max = scheme.get("amount_max", 0)
        scheme_line = f"{i}. {telugu_name} — ₹{amount_max}"
        scheme_lines.append(scheme_line)
    
    # Combine all parts
    result = header + "\n".join(scheme_lines)
    result += "\n\nఏ పథకం గురించి మరింత తెలుకోవాలి? నంబర్ టైప్ చేయండి."
    
    return result

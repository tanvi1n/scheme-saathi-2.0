import json
import os
from typing import Optional


# Keyword mapping for flexible business type matching
keyword_map = {
    "tailor": ["tailor", "tailors", "clothing", "garment"],
    "kirana": ["kirana", "grocery", "retail", "small shops", "general store"],
    "vegetable": ["vegetable", "vendor", "street vendor", "hawker", "mobile carts"],
    "salon": ["salon", "barber", "beauty", "barbers"],
    "pharmacy": ["pharmacy", "medical", "drug"],
    "laundry": ["laundry", "service providers"],
    "carpenter": ["carpenter", "carpenters", "wood"],
    "street vendor": ["street vendor", "hawker", "mobile carts", "street vendors"]
}


def discover_schemes(business_type: str, gender: str = "any", caste: str = "any") -> str:
    """
    Discover schemes matching the given business type, gender, and caste criteria.
    
    Args:
        business_type: Type of business (e.g., "Carpenters", "Street Vendors")
        gender: Gender filter ("any", "male", "female")
        caste: Caste filter ("any", "SC", "ST", "OBC", "general")
    
    Returns:
        Formatted Telugu string showing matched schemes with amounts,
        or a Telugu message if no schemes are found.
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
    
    # Filter schemes based on criteria
    matched_schemes = []
    
    # Get keyword variants for the input business type
    business_type_lower = business_type.lower()
    variants = keyword_map.get(business_type_lower, [business_type_lower])
    
    for scheme in schemes:
        # Check if business type matches using partial/substring matching
        target_types = [bt.lower() for bt in scheme.get("target_business_types", [])]
        business_match = False
        
        # Check if any variant matches any target business type
        for variant in variants:
            for target in target_types:
                if variant in target or target in variant:
                    business_match = True
                    break
            if business_match:
                break
        
        if not business_match:
            continue
        
        # Check gender eligibility
        eligibility = scheme.get("eligibility_criteria", {})
        scheme_gender = eligibility.get("gender", "any").lower()
        if gender.lower() != "any" and scheme_gender != "any" and scheme_gender != gender.lower():
            continue
        
        # Check caste eligibility
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
    result += "\n\nఏ పథకం గురించి మరింత తెలుసుకోవాలి? నంబర్ టైప్ చేయండి."
    
    return result

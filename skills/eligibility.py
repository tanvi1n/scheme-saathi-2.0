import json
import os
from typing import Dict, Any


def check_eligibility(scheme_id: str, user_profile: Dict[str, Any]) -> str:
    """
    Check if a user is eligible for a specific scheme based on their profile.
    
    Args:
        scheme_id: The ID of the scheme (e.g., "pm_vishwakarma")
        user_profile: Dict with keys: gender, caste, age, has_gst (bool), has_bank_account (bool)
    
    Returns:
        Telugu formatted string indicating eligibility status and missing requirements.
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
    
    # Find the scheme by ID
    scheme = None
    for s in schemes:
        if s.get("id") == scheme_id:
            scheme = s
            break
    
    if not scheme:
        return f"Scheme with ID '{scheme_id}' not found."
    
    # Extract eligibility criteria and scheme details
    eligibility_criteria = scheme.get("eligibility_criteria", {})
    telugu_name = scheme.get("telugu_name", scheme.get("name", "Unknown"))
    documents_required = scheme.get("documents_required", [])
    
    # Check eligibility against criteria
    missing_requirements = []
    
    # Check gender
    scheme_gender = eligibility_criteria.get("gender", "any").lower()
    user_gender = user_profile.get("gender", "").lower()
    if scheme_gender != "any" and user_gender and scheme_gender != user_gender:
        missing_requirements.append(f"성별: {scheme_gender} అవసరం (మీరు: {user_gender})")
    
    # Check caste
    scheme_caste = eligibility_criteria.get("caste", "any").lower()
    user_caste = user_profile.get("caste", "").lower()
    if scheme_caste != "any" and user_caste and scheme_caste != user_caste:
        missing_requirements.append(f"జాతి: {scheme_caste} అవసరం (మీరు: {user_caste})")
    
    # Check age (minimum)
    age_min = eligibility_criteria.get("age_min")
    user_age = user_profile.get("age")
    if age_min is not None and user_age is not None and user_age < age_min:
        missing_requirements.append(f"కనీస వయస్సు: {age_min} సంవత్సరాలు (మీరు: {user_age})")
    
    # Check age (maximum)
    age_max = eligibility_criteria.get("age_max")
    if age_max is not None and user_age is not None and user_age > age_max:
        missing_requirements.append(f"గరిష్ట వయస్సు: {age_max} సంవత్సరాలు (మీరు: {user_age})")
    
    # Check GST requirement
    gst_required = eligibility_criteria.get("gst_required", False)
    has_gst = user_profile.get("has_gst", False)
    if gst_required and not has_gst:
        missing_requirements.append("GST నమోదు అవసరం")
    
    # Check bank account requirement
    bank_account_required = eligibility_criteria.get("bank_account_required", False)
    has_bank_account = user_profile.get("has_bank_account", False)
    if bank_account_required and not has_bank_account:
        missing_requirements.append("బ్యాంక్ ఖాతా అవసరం")
    
    # Format the response
    if not missing_requirements:
        # User is fully eligible
        doc_list = "\n".join(f"  • {doc}" for doc in documents_required)
        result = f"✅ మీరు {telugu_name} కి అర్హులు!\n\nకావలసిన documents:\n{doc_list}"
        return result
    else:
        # User is missing some requirements
        missing_list = "\n".join(f"❌ {req}" for req in missing_requirements)
        result = f"⚠️ మీరు దాదాపు అర్హులు, కానీ:\n{missing_list}"
        return result

import json
import os
from typing import Dict


# Document location mapping - where to get each document
doc_locations = {
    "Aadhaar Card": "దగ్గర Aadhaar Seva Kendra లో తీయవచ్చు",
    "Mobile Number": "మీ phone number చాలు",
    "Bank Passbook": "మీ bank branch లో తీయవచ్చు",
    "Ration Card": "దగ్గర MeeSeva లో apply చేయవచ్చు",
    "Caste Certificate": "MeeSeva Center లో తీయవచ్చు (free)",
    "GST Registration": "GST portal gst.gov.in లో register చేయండి",
    "Identity Proof": "Aadhaar / Voter ID / Passport",
    "Address Proof": "Aadhaar / Electricity bill / Rent agreement",
    "Business Identity Proof": "Shop photo + rent agreement",
    "Passport Photos": "దగ్గర photo studio లో తీయవచ్చు",
    "Project Report": "DIC office సహాయం తీసుకోండి (free)",
    "Income Certificate": "MeeSeva లో తీయవచ్చు",
    "Educational Certificates": "మీ school/college certificates"
}


def get_document_guide(scheme_id: str) -> str:
    """
    Get a comprehensive document guide for a specific scheme.
    
    Args:
        scheme_id: The ID of the scheme (e.g., "pm_vishwakarma")
    
    Returns:
        Telugu formatted string with document checklist, locations, 
        application details, and helpline information.
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
    
    # Extract scheme details
    telugu_name = scheme.get("telugu_name", scheme.get("name", "Unknown"))
    documents_required = scheme.get("documents_required", [])
    apply_offline = scheme.get("apply_offline", "Information not available")
    apply_url = scheme.get("apply_url", "Information not available")
    helpline = scheme.get("helpline", "Information not available")
    
    # Build document list with locations
    doc_list = []
    for i, doc in enumerate(documents_required, 1):
        location = doc_locations.get(doc, "Online గా లేదా office మీద అడగండి")
        doc_list.append(f"{i}. {doc}\n   📌 {location}")
    
    doc_section = "\n\n".join(doc_list)
    
    # Format the complete response
    result = (
        f"📋 {telugu_name} - Documents గైడ్:\n\n"
        f"{doc_section}\n\n"
        f"📍 Apply చేయడానికి: {apply_offline}\n"
        f"🌐 Online: {apply_url}\n"
        f"📞 Helpline: {helpline}"
    )
    
    return result

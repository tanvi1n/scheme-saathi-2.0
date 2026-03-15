from skills.discover import discover_schemes
from skills.eligibility import check_eligibility
from skills.documents import get_document_guide
from typing import Dict, Any


# List of greeting words to detect
GREETINGS = ["hi", "hello", "hey", "నమస్కారం", "start", "help"]


def handle_message(user_id: str, message: str, sessions: Dict[str, Dict[str, Any]]) -> str:
    """
    Handle user message and manage conversation state.
    
    Args:
        user_id: Unique identifier for the user
        message: User's message
        sessions: Dict storing session data keyed by user_id
    
    Returns:
        Telugu response string
    """
    
    # Normalize message
    message = message.strip()
    
    # Initialize session if not exists
    if user_id not in sessions:
        sessions[user_id] = {
            "state": "start",
            "data": {
                "business_type": None,
                "matched_schemes": [],
                "current_scheme_id": None,
                "eligibility_step": 0,
                "user_profile": {}
            }
        }
    
    session = sessions[user_id]
    state = session["state"]
    data = session["data"]
    
    # Check for documents request (can happen at any time)
    if message.lower() in ["documents", "డాక్యుమెంట్స్", "docs"]:
        if data["current_scheme_id"]:
            result = get_document_guide(data["current_scheme_id"])
            return result
        else:
            return "మీరు మొదట ఏ పథకం ఎంచుకోవాలి."
    
    # START state - handle greetings
    if state == "start":
        if message.lower() in GREETINGS or not message:
            session["state"] = "awaiting_business_type"
            return ("నమస్కారం! 🙏 మీ వ్యాపార రకం ఎంచుకోండి:\n\n"
                    "1. Kirana/Grocery (కిరాణా)\n"
                    "2. Tailor (టైలర్)\n"
                    "3. Salon/Beauty (సెలూన్)\n"
                    "4. Vegetable Vendor (కూరగాయల వ్యాపారి)\n"
                    "5. Auto (ఆటో)\n"
                    "6. Other (ఇతర - టైప్ చేయండి)")
        else:
            # If not a greeting, treat as business type
            session["state"] = "awaiting_business_type"
            return handle_message(user_id, message, sessions)
    
    # AWAITING_BUSINESS_TYPE state - ask for business type
    elif state == "awaiting_business_type":
        
        # Map number to business type
        business_type_map = {
            "1": "kirana",
            "2": "tailor",
            "3": "salon",
            "4": "vegetable vendor",
            "5": "auto",
            "6": "other"
        }
        
        user_input = message.strip()
        
        # Check if user selected "other" option
        if user_input == "6" or user_input.lower() == "other":
            session["state"] = "awaiting_custom_business_type"
            return "మీ వ్యాపార రకం టైప్ చేయండి:"
        
        # Map number to business type or use direct input
        if user_input in business_type_map:
            business_type = business_type_map[user_input]
        else:
            business_type = user_input
        
        # Call discover_schemes
        schemes_result = discover_schemes(business_type)
        
        # Check if schemes were found
        if "కనుగొనబడలేదు" in schemes_result:
            return schemes_result
        
        # Parse the schemes from the result and extract scheme IDs
        # We need to also save the schemes internally
        data["business_type"] = business_type
        
        # Store the display string and ask user to choose
        session["state"] = "discovered"
        data["schemes_display"] = schemes_result
        
        # Extract scheme IDs from data to know which schemes matched
        # Re-run discover to get actual scheme objects (we need IDs)
        import json
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schemes_file = os.path.join(current_dir, "data", "schemes.json")
        
        try:
            with open(schemes_file, "r", encoding="utf-8") as f:
                all_schemes = json.load(f)
        except:
            all_schemes = []
        
        # Get keyword variants for matching
        from skills.discover import keyword_map
        business_type_lower = business_type.lower()
        variants = keyword_map.get(business_type_lower, [business_type_lower])
        
        matched_schemes = []
        for scheme in all_schemes:
            target_types = [bt.lower() for bt in scheme.get("target_business_types", [])]
            business_match = False
            for variant in variants:
                for target in target_types:
                    if variant in target or target in variant:
                        business_match = True
                        break
                if business_match:
                    break
            
            if business_match:
                matched_schemes.append(scheme)
        
        data["matched_schemes"] = matched_schemes
        
        return schemes_result
    
    # AWAITING_CUSTOM_BUSINESS_TYPE state - user types custom business
    elif state == "awaiting_custom_business_type":
        business_type = message.strip()
        
        # Call discover_schemes
        schemes_result = discover_schemes(business_type)
        
        # Check if schemes were found
        if "కనుగొనబడలేదు" in schemes_result:
            return schemes_result
        
        data["business_type"] = business_type
        
        # Get matched schemes
        import json
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        schemes_file = os.path.join(current_dir, "data", "schemes.json")
        
        try:
            with open(schemes_file, "r", encoding="utf-8") as f:
                all_schemes = json.load(f)
        except:
            all_schemes = []
        
        from skills.discover import keyword_map
        business_type_lower = business_type.lower()
        variants = keyword_map.get(business_type_lower, [business_type_lower])
        
        matched_schemes = []
        for scheme in all_schemes:
            target_types = [bt.lower() for bt in scheme.get("target_business_types", [])]
            business_match = False
            for variant in variants:
                for target in target_types:
                    if variant in target or target in variant:
                        business_match = True
                        break
                if business_match:
                    break
            
            if business_match:
                matched_schemes.append(scheme)
        
        data["matched_schemes"] = matched_schemes
        session["state"] = "discovered"
        
        return schemes_result
    
    # DISCOVERED state - user selects a scheme
    elif state == "discovered":
        try:
            choice = int(message) - 1
            if 0 <= choice < len(data["matched_schemes"]):
                scheme = data["matched_schemes"][choice]
                data["current_scheme_id"] = scheme.get("id")
                session["state"] = "eligibility"
                data["eligibility_step"] = 0
                data["user_profile"] = {}
                return "మీ వ్యక్తిగత వివరాలు అడుగుతూ ఉన్నాను...\n\n(1) మీ లింగం చెప్పండి:\n1. Male (పురుషుడు)\n2. Female (స్త్రీ)\n3. Other (ఇతర)"
            else:
                return "చెల్లని సంఖ్య. దయచేసి చెల్లుబాటుయ్యే సంఖ్య టైప్ చేయండి."
        except ValueError:
            return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్య టైప్ చేయండి."
    
    # ELIGIBILITY state - gather user profile info
    elif state == "eligibility":
        step = data["eligibility_step"]
        
        # Step 0: Gender
        if step == 0:
            gender_input = message.strip()
            if gender_input in ["1", "male", "పురుషుడు"]:
                data["user_profile"]["gender"] = "male"
                data["eligibility_step"] = 1
                return "(2) మీ కులం చెప్పండి:\n1. General\n2. SC\n3. ST\n4. OBC\n5. Minority"
            elif gender_input in ["2", "female", "స్త్రీ"]:
                data["user_profile"]["gender"] = "female"
                data["eligibility_step"] = 1
                return "(2) మీ కులం చెప్పండి:\n1. General\n2. SC\n3. ST\n4. OBC\n5. Minority"
            elif gender_input in ["3", "other", "ఇతర"]:
                data["user_profile"]["gender"] = "other"
                data["eligibility_step"] = 1
                return "(2) మీ కులం చెప్పండి:\n1. General\n2. SC\n3. ST\n4. OBC\n5. Minority"
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1, 2, లేదా 3 ఎంచుకోండి."
        
        # Step 1: Caste
        elif step == 1:
            caste_map = {"1": "general", "2": "sc", "3": "st", "4": "obc", "5": "minority"}
            caste_input = message.strip().lower()
            if caste_input in caste_map:
                data["user_profile"]["caste"] = caste_map[caste_input]
                data["eligibility_step"] = 2
                return "(3) మీ వయసు చెప్పండి (సంఖ్యలో):"
            elif caste_input in ["general", "sc", "st", "obc", "minority"]:
                data["user_profile"]["caste"] = caste_input
                data["eligibility_step"] = 2
                return "(3) మీ వయసు చెప్పండి (సంఖ్యలో):"
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1, 2, 3, 4, లేదా 5 ఎంచుకోండి."
        
        # Step 2: Age
        elif step == 2:
            try:
                age = int(message)
                if age > 0 and age < 150:
                    data["user_profile"]["age"] = age
                    data["eligibility_step"] = 3
                    return "(4) మీకు GST registration ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
                else:
                    return "చెల్లని వయస్సు. దయచేసి 1 నుండి 149 మధ్య సంఖ్య చెప్పండి."
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి మీ వయస్సు సంఖ్యలో చెప్పండి."
        
        # Step 3: GST
        elif step == 3:
            gst_input = message.strip()
            if gst_input in ["1", "yes", "అవును"]:
                data["user_profile"]["has_gst"] = True
                data["eligibility_step"] = 4
                return "(5) మీకు bank account ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
            elif gst_input in ["2", "no", "లేదు"]:
                data["user_profile"]["has_gst"] = False
                data["eligibility_step"] = 4
                return "(5) మీకు bank account ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
        
        # Step 4: Bank Account
        elif step == 4:
            bank_input = message.strip()
            if bank_input in ["1", "yes", "అవును"]:
                data["user_profile"]["has_bank_account"] = True
                session["state"] = "eligibility_result"
                result = check_eligibility(data["current_scheme_id"], data["user_profile"])
                return (
                    result + 
                    "\n\n📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n" +
                    "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
                )
            elif bank_input in ["2", "no", "లేదు"]:
                data["user_profile"]["has_bank_account"] = False
                session["state"] = "eligibility_result"
                result = check_eligibility(data["current_scheme_id"], data["user_profile"])
                return (
                    result + 
                    "\n\n📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n" +
                    "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
                )
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
    # ELIGIBILITY_RESULT state - show result and options
    elif state == "eligibility_result":
        if message.lower() in ["restart", "మళ్లీ", "మరు"]:
            session["state"] = "awaiting_business_type"
            data["business_type"] = None
            data["matched_schemes"] = []
            data["current_scheme_id"] = None
            data["eligibility_step"] = 0
            data["user_profile"] = {}
            return ("నమస్కారం! 🙏 మీ వ్యాపార రకం ఎంచుకోండి:\n\n"
                    "1. Kirana/Grocery (కిరాణా)\n"
                    "2. Tailor (టైలర్)\n"
                    "3. Salon/Beauty (సెలూన్)\n"
                    "4. Vegetable Vendor (కూరగాయల వ్యాపారి)\n"
                    "5. Auto (ఆటో)\n"
                    "6. Other (ఇతర - టైప్ చేయండి)")
        elif message.lower() in ["documents", "డాక్యుమెంట్స్", "docs"]:
            result = get_document_guide(data["current_scheme_id"])
            return result
        else:
            return "బాధ్యతలు రండి! 'documents' లేదా 'restart' చెప్పండి."
    
    # Default
    return "నమస్కారం! దయచేసి తిరిగి ప్రయత్నించండి."


if __name__ == "__main__":
    sessions = {}
    user_id = "test_user"
    print("scheme-saathi bot (type 'exit' to quit)")
    print("స్కీమ్-సాథి బాట్ (నిష్క్రమించడానికి 'exit' చెప్పండి)\n")
    
    while True:
        msg = input("You: ").strip()
        if msg == "exit":
            print("धन्यवाद! さようなら! Goodbye!")
            break
        
        response = handle_message(user_id, msg, sessions)
        print(f"Bot: {response}\n")

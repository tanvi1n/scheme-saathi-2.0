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
    
    # Check for restart request (can happen at any time)
    if message.lower() in ["restart", "మళ్లీ", "మరు"]:
        session["state"] = "awaiting_scheme_category"
        data["business_type"] = None
        data["scheme_category"] = None
        data["matched_schemes"] = []
        data["current_scheme_id"] = None
        data["eligibility_step"] = 0
        data["user_profile"] = {}
        return ("నమస్కారం! 🙏 మీరు ఏ రకమైన పథకాలు చూడాలనుకుంటున్నారు?\n\n"
                "1. Business Schemes (వ్యాపార పథకాలు)\n"
                "2. Individual Schemes (వ్యక్తిగత పథకాలు)")
    
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
            session["state"] = "awaiting_scheme_category"
            return ("నమస్కారం! 🙏 మీరు ఏ రకమైన పథకాలు చూడాలనుకుంటున్నారు?\n\n"
                    "1. Business Schemes (వ్యాపార పథకాలు)\n"
                    "2. Individual Schemes (వ్యక్తిగత పథకాలు)")
        else:
            # If not a greeting, treat as scheme category selection
            session["state"] = "awaiting_scheme_category"
            return handle_message(user_id, message, sessions)
    
    # AWAITING_SCHEME_CATEGORY state - business or individual
    elif state == "awaiting_scheme_category":
        user_input = message.strip()
        
        if user_input == "1" or user_input.lower() in ["business", "వ్యాపారం"]:
            data["scheme_category"] = "business"
            session["state"] = "awaiting_business_type"
            return ("మీ వ్యాపార రకం ఎంచుకోండి:\n\n"
                    "1. Kirana/Grocery (కిరాణా)\n"
                    "2. Tailor (టైలర్)\n"
                    "3. Salon/Beauty (సెలూన్)\n"
                    "4. Vegetable Vendor (కూరగాయల వ్యాపారి)\n"
                    "5. Auto (ఆటో)\n"
                    "6. Other (ఇతర - టైప్ చేయండి)")
        elif user_input == "2" or user_input.lower() in ["individual", "వ్యక్తిగత"]:
            data["scheme_category"] = "individual"
            session["state"] = "individual_eligibility"
            data["eligibility_step"] = 0
            data["user_profile"] = {}
            return "మీ వ్యక్తిగత వివరాలు అడుగుతూ ఉన్నాను...\n\n(1) మీ లింగం చెప్పండి:\n1. Male (పురుషుడు)\n2. Female (స్త్రీ)\n3. Other (ఇతర)"
        else:
            return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
    
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
    
    # INDIVIDUAL_ELIGIBILITY state - gather individual profile info
    elif state == "individual_eligibility":
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
                    return "(4) మీకు white ration card ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
                else:
                    return "చెల్లని వయస్సు. దయచేసి 1 నుండి 149 మధ్య సంఖ్య చెప్పండి."
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి మీ వయస్సు సంఖ్యలో చెప్పండి."
        
        # Step 3: White Ration Card
        elif step == 3:
            ration_input = message.strip()
            if ration_input in ["1", "yes", "అవును"]:
                data["user_profile"]["white_ration_card"] = True
                data["eligibility_step"] = 4
                return "(5) మీకు bank account ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
            elif ration_input in ["2", "no", "లేదు"]:
                data["user_profile"]["white_ration_card"] = False
                data["eligibility_step"] = 4
                return "(5) మీకు bank account ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
        
        # Step 4: Bank Account
        elif step == 4:
            bank_input = message.strip()
            if bank_input in ["1", "yes", "అవును"]:
                data["user_profile"]["has_bank_account"] = True
            elif bank_input in ["2", "no", "లేదు"]:
                data["user_profile"]["has_bank_account"] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
            
            # Find matching individual schemes
            import json
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            schemes_file = os.path.join(current_dir, "data", "schemes.json")
            
            try:
                with open(schemes_file, "r", encoding="utf-8") as f:
                    all_schemes = json.load(f)
            except:
                all_schemes = []
            
            # Filter individual schemes
            matched_schemes = []
            for scheme in all_schemes:
                if "target_individual_types" not in scheme:
                    continue
                
                criteria = scheme.get("eligibility_criteria", {})
                
                # Check gender
                if criteria.get("gender") != "any" and criteria.get("gender") != data["user_profile"]["gender"]:
                    continue
                
                # Check age
                age_min = criteria.get("age_min", 0)
                age_max = criteria.get("age_max", 150)
                if not (age_min <= data["user_profile"]["age"] <= (age_max or 150)):
                    continue
                
                # Check caste
                caste_req = criteria.get("caste", "any")
                if caste_req != "any":
                    allowed_castes = caste_req.split("/")
                    if data["user_profile"]["caste"] not in allowed_castes:
                        continue
                
                # Check white ration card
                if criteria.get("white_ration_card") and not data["user_profile"].get("white_ration_card"):
                    continue
                
                matched_schemes.append(scheme)
            
            if not matched_schemes:
                session["state"] = "awaiting_scheme_category"
                return "మీకు సరిపోయే పథకాలు కనుగొనబడలేదు. దయచేసి మళ్లీ ప్రయత్నించండి."
            
            # Display matched schemes
            result = f"మీకు {len(matched_schemes)} పథకాలు అర్హత ఉన్నాయి:\n\n"
            for i, scheme in enumerate(matched_schemes, 1):
                result += f"{i}. {scheme['telugu_name']} - ₹{scheme.get('amount_max', 0):,}\n"
            result += "\nఏది మరింత తెలుసుకోవాలి? (సంఖ్య టైప్ చేయండి)"
            
            data["matched_schemes"] = matched_schemes
            session["state"] = "individual_discovered"
            
            return result
    
    # INDIVIDUAL_DISCOVERED state - user selects an individual scheme
    elif state == "individual_discovered":
        try:
            choice = int(message) - 1
            if 0 <= choice < len(data["matched_schemes"]):
                scheme = data["matched_schemes"][choice]
                data["current_scheme_id"] = scheme.get("id")
                criteria = scheme.get("eligibility_criteria", {})
                
                # Check for scheme-specific questions
                # Rythu Bharosa - needs land ownership
                if scheme["id"] == "rythu_bharosa":
                    if "land_ownership_verified" not in data["user_profile"]:
                        session["state"] = "scheme_specific_question"
                        data["pending_question"] = "land_ownership"
                        return "మీకు వ్యవసాయ భూమి ఉందా?\n1. Yes (అవును)\n2. No (లేదు)"
                
                # Kalyana Lakshmi - needs income verification
                elif scheme["id"] == "kalyana_lakshmi":
                    if "annual_income" not in data["user_profile"]:
                        session["state"] = "scheme_specific_question"
                        data["pending_question"] = "annual_income"
                        return "మీ వార్షిక ఆదాయం ఎంత? (సంఖ్యలో రూపాయల్లో)"
                
                # Gruha Jyothi - needs electricity usage info
                elif scheme["id"] == "gruha_jyothi":
                    if "monthly_units" not in data["user_profile"]:
                        session["state"] = "scheme_specific_question"
                        data["pending_question"] = "monthly_units"
                        return "మీ నెలవారీ విద్యుత్ వినియోగం ఎంత? (యూనిట్లలో)"
                
                # If no additional questions needed, show result
                session["state"] = "eligibility_result"
                
                # Final eligibility check
                eligible = True
                reason = ""
                
                if scheme["id"] == "rythu_bharosa" and not data["user_profile"].get("land_ownership_verified"):
                    eligible = False
                    reason = "వ్యవసాయ భూమి అవసరం"
                elif scheme["id"] == "kalyana_lakshmi":
                    income = data["user_profile"].get("annual_income", 0)
                    if income > 200000:
                        eligible = False
                        reason = "వార్షిక ఆదాయం ₹2,00,000 కంటే తక్కువ ఉండాలి"
                elif scheme["id"] == "gruha_jyothi":
                    units = data["user_profile"].get("monthly_units", 0)
                    if units > 200:
                        eligible = False
                        reason = "నెలవారీ వినియోగం 200 యూనిట్ల కంటే తక్కువ ఉండాలి"
                
                if not eligible:
                    result = f"❌ {scheme['telugu_name']}\n\n"
                    result += f"మీరు ఈ పథకానికి అర్హులు కాదు.\n"
                    result += f"కారణం: {reason}\n\n"
                    result += "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
                    return result
                
                result = f"✅ {scheme['telugu_name']}\n\n"
                result += f"📝 వివరణ: {scheme.get('telugu_description', scheme['description'])}\n\n"
                result += f"💰 లాభం: ₹{scheme.get('amount_min', 0):,} - ₹{scheme.get('amount_max', 0):,}\n\n"
                result += "మీరు ఈ పథకానికి అర్హులు! ✅\n\n"
                result += "📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n"
                result += "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
                
                return result
            else:
                return "చెల్లని సంఖ్య. దయచేసి చెల్లుబాటుయ్యే సంఖ్య టైప్ చేయండి."
        except ValueError:
            return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్య టైప్ చేయండి."
    
    # SCHEME_SPECIFIC_QUESTION state - handle scheme-specific eligibility questions
    elif state == "scheme_specific_question":
        pending_q = data.get("pending_question")
        
        if pending_q == "land_ownership":
            user_input = message.strip()
            if user_input in ["1", "yes", "అవును"]:
                data["user_profile"]["land_ownership_verified"] = True
            elif user_input in ["2", "no", "లేదు"]:
                data["user_profile"]["land_ownership_verified"] = False
            else:
                return "చెల్లని ఇన్పుట్. దయచేసి 1 లేదా 2 ఎంచుకోండి."
        
        elif pending_q == "annual_income":
            try:
                income = int(message.strip())
                data["user_profile"]["annual_income"] = income
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్యలో టైప్ చేయండి."
        
        elif pending_q == "monthly_units":
            try:
                units = int(message.strip())
                data["user_profile"]["monthly_units"] = units
            except ValueError:
                return "చెల్లని ఇన్పుట్. దయచేసి సంఖ్యలో టైప్ చేయండి."
        
        # Clear pending question and re-process the scheme selection
        data["pending_question"] = None
        session["state"] = "individual_discovered"
        
        # Find the scheme and check eligibility
        scheme = None
        for s in data["matched_schemes"]:
            if s["id"] == data["current_scheme_id"]:
                scheme = s
                break
        
        if not scheme:
            return "ఎర్రర్. దయచేసి restart చేయండి."
        
        # Final eligibility check
        eligible = True
        reason = ""
        
        if scheme["id"] == "rythu_bharosa" and not data["user_profile"].get("land_ownership_verified"):
            eligible = False
            reason = "వ్యవసాయ భూమి అవసరం"
        elif scheme["id"] == "kalyana_lakshmi":
            income = data["user_profile"].get("annual_income", 0)
            if income > 200000:
                eligible = False
                reason = "వార్షిక ఆదాయం ₹2,00,000 కంటే తక్కువ ఉండాలి"
        elif scheme["id"] == "gruha_jyothi":
            units = data["user_profile"].get("monthly_units", 0)
            if units > 200:
                eligible = False
                reason = "నెలవారీ వినియోగం 200 యూనిట్ల కంటే తక్కువ ఉండాలి"
        
        session["state"] = "eligibility_result"
        
        if not eligible:
            result = f"❌ {scheme['telugu_name']}\n\n"
            result += f"మీరు ఈ పథకానికి అర్హులు కాదు.\n"
            result += f"కారణం: {reason}\n\n"
            result += "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
            return result
        
        result = f"✅ {scheme['telugu_name']}\n\n"
        result += f"📝 వివరణ: {scheme.get('telugu_description', scheme['description'])}\n\n"
        result += f"💰 లాభం: ₹{scheme.get('amount_min', 0):,} - ₹{scheme.get('amount_max', 0):,}\n\n"
        result += "మీరు ఈ పథకానికి అర్హులు! ✅\n\n"
        result += "📋 డాక్యుమెంట్ల కోసం, 'documents' టైప్ చేయండి.\n"
        result += "🔄 మరొక పథకం కోసం, 'restart' టైప్ చేయండి."
        
        return result
    
    # ELIGIBILITY_RESULT state - show result and options
    elif state == "eligibility_result":
        if message.lower() in ["documents", "డాక్యుమెంట్స్", "docs"]:
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

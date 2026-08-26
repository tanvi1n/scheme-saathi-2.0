import json

def audit_schemes():
    with open('data/schemes.json', 'r', encoding='utf-8') as f:
        schemes = json.load(f)
    
    print("🔍 SCHEME AUDIT REPORT\n")
    
    for scheme in schemes:
        print(f"📋 {scheme['name']} ({scheme['id']})")
        print(f"   Amount: ₹{scheme.get('amount_min', 0):,} - ₹{scheme.get('amount_max', 0):,}")
        print(f"   Interest: {scheme.get('interest_rate', 'N/A')}")
        
        criteria = scheme.get('eligibility_criteria', {})
        print(f"   Age: {criteria.get('age_min', 'Any')} - {criteria.get('age_max', 'Any')}")
        print(f"   Caste: {criteria.get('caste', 'Any')}")
        print(f"   GST Required: {criteria.get('gst_required', False)}")
        print(f"   Bank Required: {criteria.get('bank_account_required', False)}")
        print(f"   Apply URL: {scheme.get('apply_url', 'N/A')}")
        print(f"   Helpline: {scheme.get('helpline', 'N/A')}")
        print("-" * 50)

if __name__ == "__main__":
    audit_schemes()

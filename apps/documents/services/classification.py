import re

def classify_document(raw_text):
    """
    Analyzes raw text to determine the detected_type, confidence_score,
    and extracts structured fields into a dictionary.
    """
    text_lower = raw_text.lower()
    
    detected_type = 'unknown'
    confidence_score = 0.0
    extracted_data = {}
    
    # Simple keyword-based classification and extraction for prototype
    business_permit_keywords = ['business permit', 'mayor\'s permit', 'republic of the philippines', 'office of the mayor']
    contract_keywords = ['contract of lease', 'lease agreement', 'terms and conditions', 'lessor', 'lessee']
    
    bp_matches = sum(1 for kw in business_permit_keywords if kw in text_lower)
    contract_matches = sum(1 for kw in contract_keywords if kw in text_lower)
    
    if bp_matches > contract_matches and bp_matches > 0:
        detected_type = 'business_permit'
        confidence_score = min(0.98, 0.5 + (bp_matches * 0.15))
        
        # Try to extract Permit Number (e.g. "Permit No. 12345")
        permit_match = re.search(r'permit\s*no\.?[:\s]*([a-zA-Z0-9-]+)', text_lower)
        if permit_match:
            extracted_data['permit_number'] = permit_match.group(1).upper()
            
    elif contract_matches > bp_matches and contract_matches > 0:
        detected_type = 'contract'
        confidence_score = min(0.98, 0.5 + (contract_matches * 0.15))
        
    elif len(raw_text.strip()) > 50:
        # Some text found but doesn't strongly match either
        detected_type = 'other'
        confidence_score = 0.4
    else:
        # Little to no text found
        detected_type = 'unknown'
        confidence_score = 0.1
        
    return {
        'detected_type': detected_type,
        'confidence_score': confidence_score,
        'extracted_data': extracted_data
    }

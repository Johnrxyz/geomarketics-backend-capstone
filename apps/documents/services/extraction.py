from .providers import GeminiProvider, PaddleProvider
from django.conf import settings
import re

class DocumentExtractionService:
    @staticmethod
    def get_provider():
        provider = getattr(settings, 'OCR_PROVIDER', 'PADDLE')
        print(f"[OCR] Active Provider: {provider}")
        if provider == 'GEMINI':
            return GeminiProvider()
        return PaddleProvider()
        
    @staticmethod
    def detect_contract_page(raw_text):
        """
        Analyzes OCR text to detect which page of the contract it is.
        Returns a tuple: (detected_page_number: int | None, confidence: float)
        """
        text_lower = raw_text.lower()
        
        # Keywords for each page based on templates
        p1_keywords = ['pansamantalang kasunduan', 'pagpapaupa ng market stall', 'know all men by these presents', 'lessor', 'lessee']
        p2_keywords = ['pagbabawal sa sub-leasing', 'monthly rental', 'default in payment', 'sanitation', 'garbage']
        p3_keywords = ['acknowledgment', 'in witness whereof', 'notary public', 'doc no.', 'page no.']
        
        p1_score = sum(1 for kw in p1_keywords if kw in text_lower)
        p2_score = sum(1 for kw in p2_keywords if kw in text_lower)
        p3_score = sum(1 for kw in p3_keywords if kw in text_lower)
        
        scores = [(1, p1_score, len(p1_keywords)), (2, p2_score, len(p2_keywords)), (3, p3_score, len(p3_keywords))]
        scores.sort(key=lambda x: x[1], reverse=True)
        
        best_match = scores[0]
        page_num = best_match[0]
        matched_count = best_match[1]
        total_kws = best_match[2]
        
        confidence = matched_count / total_kws if total_kws > 0 else 0.0
        
        # If very little text or no strong match, return None
        if len(text_lower) < 50 or confidence < 0.3:
            return None, confidence
            
        # Give a small base confidence for passing the threshold
        confidence = min(1.0, 0.4 + (confidence * 0.6))
        return page_num, confidence

    @staticmethod
    def normalize_stall_number(raw_stall):
        """
        Normalizes stall numbers to a canonical format.
        Strips dashes, spaces, and prefixes to a consistent format (e.g. MH-14 -> H14)
        """
        if not raw_stall:
            return None
        
        # Remove all whitespace
        cleaned = re.sub(r'\s+', '', raw_stall.upper())
        
        # Remove dashes
        cleaned = cleaned.replace('-', '')
        
        # Common prefix stripping: if it starts with 'M' but the rest is a valid stall format (e.g. H14)
        # Often 'MH' is mistakenly used or 'M' is a typo for 'Market'
        # Let's extract exactly [Letters][Digits]
        match = re.search(r'([A-Z]+)(\d+)', cleaned)
        if match:
            letters = match.group(1)
            digits = match.group(2)
            # If letters is MH, normalize to H
            if letters == 'MH':
                letters = 'H'
            return f"{letters}{digits}"
            
        return cleaned

    @staticmethod
    def extract_document_data(raw_text, doc_type):
        """
        Extracts structured data based on document type templates.
        """
        text_lower = raw_text.lower()
        extracted = {}
        
        if doc_type == 'business_permit':
            # Extract Permit Number
            permit_match = re.search(r'permit\s*no\.?[:\s]*([a-zA-Z0-9-]+)', text_lower)
            if permit_match:
                extracted['permit_number'] = permit_match.group(1).upper()
                
            # Business Name
            biz_match = re.search(r'business name[:\s]*([a-zA-Z0-9\s]+?)(?:\n|registered)', text_lower)
            if biz_match:
                extracted['business_name'] = biz_match.group(1).strip().title()
                
            # Owner
            owner_match = re.search(r'registered owner[:\s]*([a-zA-Z0-9\s]+?)(?:\n|business)', text_lower)
            if owner_match:
                extracted['owner_name'] = owner_match.group(1).strip().title()
                
        elif doc_type == 'contract':
            # Extract Stall Number
            stall_match = re.search(r'market stall no\.?[:\s]*([a-zA-Z0-9-]+)', text_lower)
            if stall_match:
                raw_stall = stall_match.group(1)
                extracted['raw_stall_number'] = raw_stall.upper()
                extracted['normalized_stall_number'] = DocumentExtractionService.normalize_stall_number(raw_stall)
                
            # Vendor Name
            vendor_match = re.search(r'lessee[:\s]*([a-zA-Z0-9\s,]+?)(?:\n|with)', text_lower)
            if vendor_match:
                extracted['vendor_name'] = vendor_match.group(1).strip().title()

        return extracted

    @staticmethod
    def classify_document(raw_text):
        """
        Determines document type from combined text.
        """
        text_lower = raw_text.lower()
        
        bp_keywords = ['business permit', "mayor's permit", 'office of the mayor']
        contract_keywords = ['contract of lease', 'pansamantalang kasunduan', 'lessee']
        
        bp_matches = sum(1 for kw in bp_keywords if kw in text_lower)
        contract_matches = sum(1 for kw in contract_keywords if kw in text_lower)
        
        if bp_matches > contract_matches and bp_matches > 0:
            doc_type = 'business_permit'
            confidence = min(0.98, 0.5 + (bp_matches * 0.15))
        elif contract_matches > bp_matches and contract_matches > 0:
            doc_type = 'contract'
            confidence = min(0.98, 0.5 + (contract_matches * 0.15))
        elif len(text_lower) > 50:
            doc_type = 'other'
            confidence = 0.4
        else:
            doc_type = 'unknown'
            confidence = 0.1
            
        extracted_data = DocumentExtractionService.extract_document_data(raw_text, doc_type)
            
        return {
            'detected_type': doc_type,
            'confidence_score': confidence,
            'extracted_data': extracted_data
        }

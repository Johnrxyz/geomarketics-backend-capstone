import base64
import json
import os
from abc import ABC, abstractmethod

class BaseOCRProvider(ABC):
    @abstractmethod
    def process_document(self, file_paths, doc_type="contract"):
        """
        Accepts a list of file paths.
        Returns a list of extracted dictionaries corresponding to each page.
        """
        pass

class GeminiProvider(BaseOCRProvider):
    def __init__(self):
        from django.conf import settings
        
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not self.api_key:
            print("[OCR] Warning: GEMINI_API_KEY is missing. Gemini extraction will fail.")
            
        print("[OCR] Initializing Gemini Provider via CLI Process...")
        self.cli_path = os.path.join(os.path.dirname(__file__), 'gemini_cli.py')

    def process_document(self, file_paths, doc_type="contract"):
        results = []
        for path in file_paths:
            try:
                results.append(self._analyze_single_page(path, doc_type))
            except Exception as e:
                print(f"[Gemini Error] {e}")
                results.append({
                    "raw_text": "",
                    "page_number": None,
                    "confidence": 0.0,
                    "extracted_data": {}
                })
        return results

    def _analyze_single_page(self, file_path, doc_type):
        import subprocess
        import sys
        
        try:
            result = subprocess.run(
                [sys.executable, self.cli_path, file_path, doc_type],
                capture_output=True,
                text=True,
                check=True
            )
            stdout = result.stdout.strip()
            
            # The CLI prints the JSON result
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                # If there was an error string printed or something unparsable
                print(f"[Gemini Error] Unparsable CLI output: {stdout}")
                return {"raw_text": stdout, "page_number": None, "confidence": 0.0, "extracted_data": {}}
                
            if "error" in data:
                print(f"[Gemini API Error] {data['error']}")
                return {"raw_text": "", "page_number": None, "confidence": 0.0, "extracted_data": {}}

        except subprocess.CalledProcessError as e:
            print(f"[Gemini CLI Error] Process failed. Return code: {e.returncode}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
            return {"raw_text": "", "page_number": None, "confidence": 0.0, "extracted_data": {}}

        # Map to expected structure
        extracted = {}
        # Basic server-side validation to prevent NoneType errors in DB
        try:
            page_num = int(data.get("page_number")) if data.get("page_number") else None
        except (ValueError, TypeError):
            page_num = None

        try:
            confidence = float(data.get("confidence_score", 0.0))
        except (ValueError, TypeError):
            confidence = 0.0

        return {
            "raw_text": data.get("raw_text", ""),
            "page_number": page_num,
            "confidence": confidence,
            "extracted_data": extracted
        }

    def _build_prompt(self, doc_type):
        if doc_type == "contract":
            return """
            Analyze this page of a public market stall lease contract.
            Return a JSON object with EXACTLY these keys:
            - "raw_text": A string containing all the text you can read.
            - "page_number": An integer (1, 2, or 3) indicating which page of the contract this is. If you cannot confidently determine the page number, return null.
            - "confidence_score": A float between 0.0 and 1.0 indicating your confidence in the page number and extracted data.
            - "vendor_name": The name of the vendor (Lessee) if found, else null.
            - "business_name": The name of the business if found, else null.
            - "stall_number": The stall number (e.g. A-01 or H14) if found, else null.
            """
        else:
            return """
            Analyze this business permit document.
            Return a JSON object with EXACTLY these keys:
            - "raw_text": A string containing all the text you can read.
            - "page_number": Always 1.
            - "confidence_score": A float between 0.0 and 1.0 indicating your confidence.
            - "permit_number": The permit number if found, else null.
            - "business_name": The business name if found, else null.
            - "registered_owner": The owner's name if found, else null.
            - "business_address": The business address if found, else null.
            - "expiration_date": The expiration date if found, else null.
            - "line_of_business": The line of business if found, else null.
            """

class PaddleProvider(BaseOCRProvider):
    def process_document(self, file_paths, doc_type="contract"):
        from .ocr import extract_text_paddleocr
        from .extraction import DocumentExtractionService
        
        ocr_results = extract_text_paddleocr(file_paths)
        results = []
        for path in file_paths:
            raw_text = ocr_results.get(path, "")
            if doc_type == "contract":
                page_num, conf = DocumentExtractionService.detect_contract_page(raw_text)
                results.append({
                    "raw_text": raw_text,
                    "page_number": page_num,
                    "confidence": conf,
                    "extracted_data": {} # Paddle extraction is done later via classify_document
                })
            else:
                results.append({
                    "raw_text": raw_text,
                    "page_number": 1,
                    "confidence": 1.0,
                    "extracted_data": {}
                })
        return results

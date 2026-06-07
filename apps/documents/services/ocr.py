import os
import sys
import json
import subprocess

def extract_text_paddleocr(file_paths):
    """
    Uses PaddleOCR to extract text from images and PDFs.
    Runs in an isolated subprocess to prevent thread deadlocks on Windows.
    Accepts a list of file paths and returns a dictionary of extracted texts.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]
        
    if not file_paths:
        return {}
        
    try:
        cli_script = os.path.join(os.path.dirname(__file__), 'paddle_cli.py')
        
        # Run the isolated script and wait for it to finish (with a timeout of 60 seconds per file)
        timeout = 60 * len(file_paths)
        print(f"[OCR START] Spawning isolated process for {len(file_paths)} files")
        result = subprocess.run(
            [sys.executable, cli_script, *file_paths],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            print(f"[OCR ERROR] Process failed with code {result.returncode}:\n{result.stderr}")
            return {p: "" for p in file_paths}
            
        try:
            data = json.loads(result.stdout.strip())
            if "error" in data:
                print(f"[OCR ERROR] {data['error']}")
                return {p: "" for p in file_paths}
            print(f"[OCR END] Successfully extracted text for {len(file_paths)} files")
            return data.get("results", {})
        except json.JSONDecodeError:
            print(f"[OCR ERROR] Invalid JSON from subprocess:\n{result.stdout}")
            return {p: "" for p in file_paths}
            
    except subprocess.TimeoutExpired:
        print(f"[OCR ERROR] Process timed out after {timeout} seconds")
        return {p: "" for p in file_paths}
    except Exception as e:
        print(f"PaddleOCR extraction failed: {e}")
        return {p: "" for p in file_paths}

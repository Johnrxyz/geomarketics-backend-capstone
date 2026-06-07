import sys
import traceback

def main():
    import json as sys_json
    
    if len(sys.argv) < 2:
        print(sys_json.dumps({"error": "No file path provided"}))
        sys.exit(1)
        
    file_paths = sys.argv[1:]
    results_dict = {}
    
    try:
        from paddleocr import PaddleOCR
        # Initialize OCR once, optimized for CPU speed
        # use_textline_orientation=False skips a heavy model run per text box
        ocr = PaddleOCR(use_textline_orientation=False, lang='en', show_log=False)
        
        for file_path in file_paths:
            result = ocr.ocr(file_path, cls=True)
            
            if not result or not result[0]:
                results_dict[file_path] = ""
                continue
                
            raw_text = ""
            for line in result[0]:
                text = line[1][0]
                raw_text += text + "\n"
                
            results_dict[file_path] = raw_text.strip()
            
        print(sys_json.dumps({"results": results_dict}))
        
    except Exception as e:
        import json as err_json
        print(err_json.dumps({"error": str(e), "traceback": traceback.format_exc()}))
        sys.exit(1)

if __name__ == "__main__":
    main()

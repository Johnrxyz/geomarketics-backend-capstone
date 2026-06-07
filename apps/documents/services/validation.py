import cv2
import numpy as np

def validate_image_quality(file_stream):
    """
    Checks for blurriness, brightness, and readability using OpenCV.
    Returns a list of warnings (e.g., "Document appears blurry").
    """
    warnings = []
    
    try:
        # file_stream is an InMemoryUploadedFile or TemporaryUploadedFile
        # Rewind stream before reading
        file_stream.seek(0)
        file_bytes = np.frombuffer(file_stream.read(), np.uint8)
        file_stream.seek(0)  # Rewind again for subsequent operations
        
        # Decode image
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None:
            return warnings # Maybe it's a PDF or unrecognized image format
            
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 1. Check Blurriness using Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 100.0: # threshold
            warnings.append("Document appears blurry.")
            
        # 2. Check Brightness
        brightness = np.mean(gray)
        if brightness < 50:
            warnings.append("Image is too dark.")
        elif brightness > 230:
            warnings.append("Image is too bright/washed out.")
            
    except Exception as e:
        # Non-fatal error, likely a non-image document (like PDF)
        pass
        
    return warnings

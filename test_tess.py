# test_tess.py
import pytesseract
import os

print(f"Current os.environ['PATH']: {os.environ.get('PATH')}") # See what Python sees

try:
    # Explicitly tell pytesseract where tesseract.exe is.
    # Adjust this path if yours is different. This is common for UB Mannheim install.
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
    
    version = pytesseract.get_tesseract_version()
    print(f"SUCCESS: Pytesseract found Tesseract version: {version}")
    
    # Try a simple OCR on a dummy image if you have one, or skip this part
    # from PIL import Image
    # try:
    #     # Create a dummy image with text or use an existing one
    #     # For example, if you have 'logs/ocr_test_input.png' from AnalysisEngine test
    #     text = pytesseract.image_to_string(Image.open("logs/ocr_test_input.png"))
    #     print(f"OCR Result: '{text.strip()}'")
    # except Exception as e_img:
    #     print(f"Could not OCR dummy image: {e_img}")

except pytesseract.TesseractNotFoundError:
    print("FAIL: TesseractNotFoundError. Pytesseract could not find tesseract.exe even with explicit path or via system PATH.")
    print("Ensure the path above is correct and tesseract.exe exists there.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
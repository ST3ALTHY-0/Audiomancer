import asyncio
import re
import pytesseract
from PIL import Image
from typing import Optional

class OCRService:
    """Handles OCR text extraction"""
    
    def __init__(self, tesseract_path: str):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        self._lock = asyncio.Lock()
    
    async def extract_text(self, image: Image.Image) -> Optional[str]:
        """Extract and clean text from image"""
        try:
            async with self._lock:
                text = await asyncio.to_thread(pytesseract.image_to_string, image)
        except Exception as e:
            print(f"OCR error: {e}")
            return None
        
        # Clean up text
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace("- ", "")
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")
        # so far TTS is having problems with contractions like can't/won't, It's and so on, might have to uncontractionize them here
        
        return text if text else None
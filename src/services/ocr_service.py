import asyncio
import re
import pytesseract
import cv2
import numpy as np
from PIL import Image
from typing import Optional
from pathlib import Path

class OCRService:
    """Handles OCR text extraction"""
    
    def __init__(self, tesseract_path: str):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        self._lock = asyncio.Lock()
    
    async def extract_text(self, image: Image.Image) -> Optional[str]:
        """Extract and clean text from image"""
        try:
            # Save image to debug folder (overwrites previous)
            debug_dir = Path("debug_images")
            debug_dir.mkdir(exist_ok=True)
            debug_path = debug_dir / "latest_ocr_image.png"
            # image.save(debug_path)
            
            # Preprocess image for OCR
            preprocessed = self.preprocess_for_ocr(image)
            
            image.save(debug_path)

            
            async with self._lock:
                config = "--oem 1 --psm 6 -l eng"
                text = await asyncio.to_thread(
                    pytesseract.image_to_string,
                    preprocessed,
                    config=config
                )           
        except Exception as e:
            print(f"OCR error: {e}")
            return None
        
        # Clean up text
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace("- ", "") # meant to remove hyphens braking up words between lines, could break hyphens that are meant to be there
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")
        # so far VITS TTS is having problems with contractions like can't/won't, It's and so on, might have to uncontractionize them here
        
        return text if text else None

    def preprocess_for_ocr(self, img):
        if isinstance(img, np.ndarray) is False:
            img = np.array(img)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        gray = cv2.resize(
            gray, None, fx=2, fy=2,
            interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.medianBlur(gray, 3)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 2
        )

        return thresh
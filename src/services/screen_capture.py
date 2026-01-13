import win32gui
import win32ui
import win32con
from PIL import Image
import ctypes
from typing import Optional, Tuple

class ScreenCaptureService:
    """Handles window screenshot capture"""
    
    def __init__(self):
        # Set DPI awareness once
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    
    def capture_window(self, hwnd: int, crop: Optional[Tuple[int, int, int, int]] = None) -> Optional[Image.Image]:
        """Capture window client area to PIL Image"""
        rect = win32gui.GetClientRect(hwnd)
        width = rect[2]
        height = rect[3]

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 1)

        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                               bmpstr, 'raw', 'BGRX', 0, 1)

        # Cleanup
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        if crop:
            left, top, right, bottom = crop
            img = img.crop((left, top, width - right, height - bottom))

        if not img.getbbox():
            return None

        return img
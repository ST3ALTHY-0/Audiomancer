import win32api
import win32con
from pygetwindow import getAllWindows
from typing import Optional

class KindleController:
    """Handles Kindle window operations"""
    
    def __init__(self):
        self._window = None
    
    def find_window(self):
        """Find and store Kindle window"""
        for w in getAllWindows():
            if "Kindle for PC" in w.title:
                self._window = w
                return w
        return None
    
    @property
    def window(self):
        return self._window
    
    @property
    def hwnd(self):
        return self._window._hWnd if self._window else None
    
    def is_valid(self) -> bool:
        """Check if window still exists"""
        if not self._window:
            return False
        try:
            import win32gui
            return win32gui.IsWindow(self._window._hWnd)
        except Exception:
            return False
    
    def turn_page(self) -> None:
        """Send page turn command"""
        if self._window:
            win32api.PostMessage(self._window._hWnd, win32con.WM_KEYDOWN, win32con.VK_RIGHT, 0)
            win32api.PostMessage(self._window._hWnd, win32con.WM_KEYUP, win32con.VK_RIGHT, 0)
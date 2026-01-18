import win32api
import win32con
from pygetwindow import getAllWindows
from typing import Optional, List

class WindowController:
    """Handles window operations for OCR reading"""
    
    def __init__(self):
        self._window = None
    
    def get_all_windows(self) -> List[str]:
        """Get list of all available window titles"""
        windows = []
        for w in getAllWindows():
            if w.title and w.title.strip():  # Only include windows with titles
                windows.append(w.title)
        return windows
    
    #Someone might not want this exact functionality, but it fits my use case nicely so change it if you want
    def find_window(self, window_title: Optional[str] = None):
        """Find and store window by title. Tries exact match first, then partial match on first 20 chars"""
        if not window_title:
            return None
        
        # Try exact match first (case-insensitive contains)
        for w in getAllWindows():
            if window_title.lower() in w.title.lower():
                self._window = w
                return w
        
        # Try partial match on first 20 characters
        search_prefix = window_title[:20].lower()
        partial_matches = []
        for w in getAllWindows():
            if w.title and len(w.title) >= len(search_prefix):
                if w.title[:len(search_prefix)].lower() == search_prefix:
                    partial_matches.append(w)
        
        # If exactly one partial match found, use it
        if len(partial_matches) == 1:
            self._window = partial_matches[0]
            return partial_matches[0]
        
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
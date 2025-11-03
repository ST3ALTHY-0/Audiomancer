import asyncio
import re
from pywinauto import Application
import pygetwindow as gw
import win32gui
import win32con
import win32ui
from PIL import Image
import pytesseract
import win32api
from pytesseract import TesseractError
# -------------------- Configuration --------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TTS_EXE = r"C:\Programming\CPP\NaturalVoiceSAPIAdapter\ttsapplication\TTSApplicationSample\x64\Debug\TtsApplication.exe"


CROP_LEFT = 75
CROP_TOP = 110
CROP_RIGHT = 20
CROP_BOTTOM = 50
PAGE_DELAY = 0.1  # seconds
# PAGE_DELAY = 0.5  # seconds

# Prevent concurrent Tesseract invocations which can cause crashes/leaks on Windows
ocr_lock = asyncio.Lock()
TTS_VOICE = "Microsoft Andrew Online (Natural)"
TTS_VOLUME = "100"
TTS_RATE = "1.1"


#"Microsoft Guy Online (Natural) - English (United States)"
# Microsoft Andrew Online (Natural)
# Microsoft Eric Online (Natural) - English (United States)

# -------------------- Background Screenshot --------------------
def capture_window_bg(hwnd, crop=None):
    """Capture window in background; no focus or restore."""
    rect = win32gui.GetClientRect(hwnd)
    width = rect[2]
    height = rect[3]

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)

    import ctypes
    ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 1)

    bmpinfo = save_bitmap.GetInfo()
    bmpstr = save_bitmap.GetBitmapBits(True)
    img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)

    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    if crop:
        left, top, right, bottom = crop
        img = img.crop((left, top, width - right, height - bottom))

    return img



# -------------------- TTS --------------------
async def speak_async(text):
    """Speaks text asynchronously via external TTS app."""
    args = [
        TTS_EXE,
        "--voice", TTS_VOICE,
        "--volume", TTS_VOLUME,
        "--rate", TTS_RATE,
        text,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(*args)
        await proc.wait()
    except asyncio.CancelledError:
        try:
            proc.kill()
        except Exception:
            pass
        raise
    except Exception as e:
        print(f"TTS error: {e}")
        
def estimate_speech_duration(text, rate=1.0):
    """
    Estimate how long it will take to speak `text` in seconds.
    - text: string of page text
    - rate: TTS rate, 1.0 = normal
    """
    words = len(text.split())
    # base WPM at rate=1.0
    base_wpm = 160
    wpm = base_wpm * rate
    duration_seconds = (words / wpm) * 60
    return duration_seconds


# -------------------- Kindle Helpers --------------------
def find_kindle_window():
    """Find the Kindle window."""
    for w in gw.getAllWindows():
        if "Kindle" in w.title:
            return w
    return None


def turn_page(kindle_window):
    """Simulates right-arrow key to turn the page using pywinauto."""
    try:
        app = Application(backend="uia").connect(handle=kindle_window._hWnd)
        win = app.window(handle=kindle_window._hWnd)
        win.type_keys("{RIGHT}")
        print("Page turned")
        return True
    except Exception as e:
        print(f"Failed to turn page: {e}")
        return False
    
def turn_page_bg(hwnd):
    """Send a right-arrow key press directly to the window (background)."""
    # WM_KEYDOWN + WM_KEYUP for right arrow
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RIGHT, 0)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RIGHT, 0)


# -------------------- Main Reader --------------------
async def read_kindle_text_async(kindle_window):
    if not kindle_window:
        print("Kindle window not found.")
        return

    # Capture screenshot in background first
    # annoying delay processing text
    screenshot = capture_window_bg(kindle_window._hWnd,
                                   crop=(CROP_LEFT, CROP_TOP, CROP_RIGHT, CROP_BOTTOM))

    # OCR with thread + lock
    try:
        async with ocr_lock:
            text = await asyncio.to_thread(pytesseract.image_to_string, screenshot)
    except TesseractError as e:
        print(f"TesseractError during OCR: {e}")
        return
    except Exception as e:
        print(f"Unexpected error during OCR: {e}")
        return

    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace("- ", "")

    if not text:
        print("No text detected on this page.")
        return
    print("Detected text:\n", text)
    await speak_async(text)


async def main_loop():
    kindle_win = find_kindle_window()
    if not kindle_win:
        print("Kindle window not found. Open Kindle and try again.")
        return

    try:
        while True:
            await read_kindle_text_async(kindle_win)
            turn_page_bg(kindle_win._hWnd)
            await asyncio.sleep(PAGE_DELAY)
    except asyncio.CancelledError:
        print("Main loop cancelled. Exiting...")
    except KeyboardInterrupt:
        print("Exiting...")


if __name__ == "__main__":
    print("Starting background Kindle TTS reader. Press Ctrl+C to stop.")
    asyncio.run(main_loop())

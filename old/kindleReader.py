# kindle_reader.py
import asyncio
import re
from typing import Optional
from concurrent.futures import ProcessPoolExecutor
# from pywinauto import Application # needed if you dont have ctypes.windll.user32.SetProcessDPIAware()
from pygetwindow import getAllWindows
import win32gui
import win32con
import win32ui
from PIL import Image
import pytesseract
import win32api
import config
from utils import resource_path
import ctypes

pytesseract.pytesseract.tesseract_cmd = resource_path(config.TESSERACT_PATH)
tts_server_proc = None
ocr_executor: Optional[ProcessPoolExecutor] = None
ocr_lock = asyncio.Lock()
DEBUG_SAVE = False
DEBUG_DIR = r"c:\Programming\Python\kindleReader\debug_images"

# make python aware of our dpi (needed for screens that dont have scaling set to 100%, like 4k/2k screens at 125/150% scaling)
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

def _to_str_arg(v):
    return str(v) if v is not None else ""

# -------------------- Screenshot --------------------
def capture_window_bg(hwnd, crop=None):
    """
    Capture window client area to a PIL.Image
    """
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

    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    if crop:
        left, top, right, bottom = crop
        img = img.crop((left, top, width - right, height - bottom))

    if not img.getbbox():
        # getbbox() returns None for a fully blank image
        return None

    return img

# -------------------- Kindle Controls --------------------
def find_kindle_window():
    for w in getAllWindows():
        if "Kindle for PC" in w.title:
            return w
    return None


def turn_page_bg(hwnd):
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RIGHT, 0)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RIGHT, 0)


# -------------------- TTS --------------------
async def start_tts_server_once():
    """
    Starts TTS server if configured and not already started.
    Ensures args are strings to avoid TypeError.
    """
    global tts_server_proc
    if tts_server_proc is None and config.TTS_USE_TCP and config.TTS_SERVER_AUTO_START:
        try:
            tts_server_proc = await asyncio.create_subprocess_exec(
                resource_path(config.TTS_EXE_PATH),
                "--server", 
                "--voice", str(config.TTS_VOICE),
                "--rate", str(config.TTS_RATE),
                "--volume", str(config.TTS_VOLUME)
            )
            # wait until the TCP server is actually accepting connections
            # try to connect a few times rather than sleeping a fixed amount
            for i in range(10):
                try:
                    reader, writer = await asyncio.open_connection(config.TTS_SERVER_HOST, config.TTS_SERVER_PORT)
                    writer.close()
                    await writer.wait_closed()
                    break
                except Exception:
                    await asyncio.sleep(0.25)
        except Exception as e:
            print(f"Failed to start TTS server: {e}")
            tts_server_proc = None


async def speak_async(text):
    #TODO: want to add server to send message when its about to finish reading from its buffer,
    #So we can take a pic and send more text just before its done reading
    if config.TTS_USE_TCP:
        await start_tts_server_once()
        try:
            reader, writer = await asyncio.open_connection(config.TTS_SERVER_HOST, config.TTS_SERVER_PORT)
            safe_text = text.replace("\n", " ").replace("\r", " ")
            writer.write((safe_text + "\n").encode("utf-8"))
            await writer.drain()

            # Attempt to read any response the server sends back (e.g., "almost done" notifications)
            try:
                resp = await asyncio.wait_for(reader.read(4096), timeout=2.0)
                if resp:
                    try:
                        resp_text = resp.decode('utf-8', errors='replace').strip()
                    except Exception:
                        resp_text = str(resp)
                    print(f"[TTS server] {resp_text}")
            except asyncio.TimeoutError:
                # no response within timeout; that's fine
                pass

            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"TTS TCP send error: {e}")


async def send_tts_command_async(command: str, read_timeout: float = 2.0):
    """Send a raw command line to the TTS server and print any response.

    This is intended for control messages like:
      "voice Microsoft Zira"
      "rate -2.5"
      "volume 80"
    """
    if config.TTS_USE_TCP:
        await start_tts_server_once()
        try:
            reader, writer = await asyncio.open_connection(config.TTS_SERVER_HOST, config.TTS_SERVER_PORT)
            payload = command.replace("\n", " ").replace("\r", " ") + "\n"
            print(f"[TTS client] Sending: {payload.strip()}")
            writer.write(payload.encode("utf-8"))
            await writer.drain()

            try:
                resp = await asyncio.wait_for(reader.read(4096), timeout=read_timeout)
                if resp:
                    try:
                        resp_text = resp.decode('utf-8', errors='replace').strip()
                    except Exception:
                        resp_text = str(resp)
                    print(f"[TTS server] {resp_text}")
                    return resp_text
            except asyncio.TimeoutError:
                # no immediate response
                return None
            finally:
                writer.close()
                await writer.wait_closed()
        except Exception as e:
            print(f"send_tts_command error: {e}")
            return None
    else:
        print("TTS TCP mode disabled; not sending command.")
        return None


# -------------------- OCR + Reading --------------------
def estimate_speech_duration(text, rate=1.1):
    words = len(text.split())
    base_wpm = 225
    try:
        r = float(rate)
    except (ValueError, TypeError):
        print(f"Invalid TTS rate '{rate}', defaulting to 1.1")
        r = 1.1  # Use the default parameter value
    wpm = base_wpm * r
    return (words / wpm) * 60


async def read_kindle_text_async(kindle_window):
    if not kindle_window:
        print("Kindle window not found.")
        return None

    screenshot = capture_window_bg(kindle_window._hWnd,
                                   crop=(config.CROP_LEFT, config.CROP_TOP, config.CROP_RIGHT, config.CROP_BOTTOM))
    # show the screenshot for debugging (will bring window to foreground)
    
    if screenshot is None:
        print("Screenshot is blank/empty.")
        return None

    try:
        async with ocr_lock:
            text = await asyncio.to_thread(pytesseract.image_to_string, screenshot)
    except Exception as e:
        print(f"OCR error: {e}")
        return None

    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace("- ", "")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")

    if not text:
        print("No text detected on this page.")
        return None

    print("Detected text:\n", text)
    return text


async def main_loop(stop_event):
    kindle_win = find_kindle_window()
    if not kindle_win:
        print("Kindle window not found. Open Kindle and try again.")
        return
    #Make sure we start the server
    if config.TTS_USE_TCP:
        await start_tts_server_once()

    while not stop_event.is_set():
        # Re-validate window still exists
        try:
            if not win32gui.IsWindow(kindle_win._hWnd):
                print("Kindle window closed.")
                break
        except Exception:
            print("Kindle window no longer valid.")
            break
            
        text = await read_kindle_text_async(kindle_win)
        if text:
            await speak_async(text)
            duration = estimate_speech_duration(text, config.TTS_RATE)
            await asyncio.sleep(duration)
            turn_page_bg(kindle_win._hWnd)
        else:
            await asyncio.sleep(1)
            print("No Text Error, waiting 1 sec")

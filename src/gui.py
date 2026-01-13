# gui.py
import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import time
import sys

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # SYSTEM_AWARE
    except Exception as e:
        print(f"DPI awareness setup failed: {e}")

from orchestrator import KindleReaderOrchestrator
from services.tts_python import CoquiTTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.kindle_controller import KindleController
import config

class KindleTTSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kindle TTS Reader")
        self.root.geometry("900x500")
        self.root.minsize(800, 450)

        # Center window
        self.root.update_idletasks()
        width, height = 900, 500
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Async loop for orchestrator
        self.loop = asyncio.new_event_loop()
        self.stop_event = asyncio.Event()
        self.orchestrator = None

        # --- TTS SETTINGS PANEL ---
        left = ttk.Frame(root, padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left, text="TTS Settings", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        self.voice_var = tk.StringVar(value=getattr(config, "COQUI_VOICE", "p254"))
        self.rate_var = tk.StringVar(value=str(getattr(config, "TTS_RATE", 1.0)))
        self.volume_var = tk.StringVar(value=str(getattr(config, "TTS_VOLUME", 100)))

        self.tts_service = None  # Will be set in _run_orchestrator

        # Trace changes to update TTS settings live
        self.voice_var.trace_add('write', self._on_voice_change)
        self.rate_var.trace_add('write', self._on_rate_change)
        self.volume_var.trace_add('write', self._on_volume_change)

        ttk.Label(left, text="Voice:").pack(anchor=tk.W)
        ttk.Entry(left, textvariable=self.voice_var, width=35).pack(anchor=tk.W)
        ttk.Label(left, text="Rate:").pack(anchor=tk.W)
        ttk.Entry(left, textvariable=self.rate_var, width=35).pack(anchor=tk.W)
        ttk.Label(left, text="Volume:").pack(anchor=tk.W)
        ttk.Entry(left, textvariable=self.volume_var, width=35).pack(anchor=tk.W)

        ttk.Separator(left).pack(fill=tk.X, pady=10)

        # --- CONTROL BUTTONS ---
        self.start_btn = ttk.Button(left, text="▶ Start Reading", command=self.start)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(left, text="■ Stop", command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # --- STATUS PANEL ---
        ttk.Separator(left).pack(fill=tk.X, pady=10)
        ttk.Label(left, text="Status", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(left, textvariable=self.status_var, foreground="gray").pack(anchor=tk.W)

        ttk.Label(left, text="Current Page:").pack(anchor=tk.W, pady=(10,0))
        self.page_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.page_var, wraplength=400, justify="left").pack(anchor=tk.W)

        ttk.Label(left, text="Current Sentence:").pack(anchor=tk.W, pady=(10,0))
        self.sentence_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.sentence_var, wraplength=400, justify="left", foreground="blue").pack(anchor=tk.W)

        ttk.Label(left, text="Time Remaining:").pack(anchor=tk.W, pady=(10,0))
        self.remaining_var = tk.StringVar(value="0.0s")
        ttk.Label(left, textvariable=self.remaining_var, foreground="red").pack(anchor=tk.W)

    # -------------------- ORCHESTRATOR CONTROL --------------------
    def start(self):
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("Initializing...")

        # Reset stop event
        self.stop_event.clear()

        # Launch orchestrator in background thread
        threading.Thread(target=self._run_orchestrator, daemon=True).start()

    def _set_status_safe(self, msg):
        self.root.after(0, lambda: self.status_var.set(msg))

    def stop(self):
        if self.orchestrator:
            self.loop.call_soon_threadsafe(self.stop_event.set)
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")

    def _run_orchestrator(self):
        asyncio.set_event_loop(self.loop)
        try:
            self._set_status_safe("Initializing TTS service...")
            self.tts_service = CoquiTTSService(
                model=getattr(config, 'COQUI_MODEL', 'tts_models/en/vctk/vits'),
                voice=self.voice_var.get(),
                rate=float(self.rate_var.get()),
                volume=int(self.volume_var.get()),
                espeak_path=getattr(config, 'COQUI_ESPEAK_PATH', None),
            )
            self._set_status_safe("Initializing Kindle controller...")
            kindle = KindleController()
            self._set_status_safe("Initializing screen capture...")
            screen_capture = ScreenCaptureService()
            self._set_status_safe("Initializing OCR service...")
            ocr = OCRService(config.TESSERACT_PATH)
            self.orchestrator = KindleReaderOrchestrator(self.tts_service, kindle, screen_capture, ocr)

            self._set_status_safe("Starting reading loop...")
            # Run orchestrator with GUI callbacks for status updates
            self.loop.run_until_complete(self.orchestrator.run_with_callbacks(
                stop_event=self.stop_event,
                on_page_update=self._update_page,
                on_sentence_update=self._update_sentence,
                on_time_update=self._update_remaining
            ))
            self._set_status_safe("Stopped")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._set_status_safe(f"Error: {e}\n{tb}")
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def _on_voice_change(self, *args):
        if self.tts_service:
            self.tts_service.set_voice(self.voice_var.get())

    def _on_rate_change(self, *args):
        if self.tts_service:
            try:
                self.tts_service.set_rate(float(self.rate_var.get()))
            except ValueError:
                pass

    def _on_volume_change(self, *args):
        if self.tts_service:
            try:
                self.tts_service.set_volume(int(self.volume_var.get()))
            except ValueError:
                pass

    # -------------------- CALLBACKS --------------------
    def _update_page(self, text: str):
        self.root.after(0, lambda: self.page_var.set(text[:500]))  # limit length

    def _update_sentence(self, text: str):
        self.root.after(0, lambda: self.sentence_var.set(text))

    def _update_remaining(self, seconds: float):
        self.root.after(0, lambda: self.remaining_var.set(f"{seconds:.1f}s"))


if __name__ == "__main__":
    root = tk.Tk()
    app = KindleTTSApp(root)
    root.mainloop()

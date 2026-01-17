import sys
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import os
import json

from orchestrator import KindleReaderOrchestrator
from services.tts_python import CoquiTTSService
from services.tts_realtime import RealTimeTTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.kindle_controller import KindleController
import config
from xtts_client import stream_tts, play_stream

class KindleTTSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kindle TTS Reader")
        self.root.geometry("900x500")
        self.root.minsize(800, 450)

        # DPI scaling
        try:
            scaling = root.winfo_fpixels("1i") / 72
            root.tk.call("tk", "scaling", scaling)
            root.option_add("*Font", "SegoeUI 10")
        except Exception:
            pass

        # Async loop
        self.loop = asyncio.new_event_loop()
        self.stop_event = asyncio.Event()
        self.orchestrator = None
        self.tts_service = None
        self.current_reference_audio = None

        # -------------------- UI --------------------
        self.left = ttk.Frame(root, padding=10)
        self.left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right pane for page preview/status
        self.right = ttk.Frame(root, padding=(0, 10, 10, 10))
        self.right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Load voices
        voices_path = os.path.join(os.path.dirname(__file__), "voices", "coquiVoices.json")
        with open(voices_path, "r", encoding="utf-8") as f:
            self.voice_data = json.load(f)

        self.models = sorted({v["model"] for v in self.voice_data})
        self.model_to_voices = {}
        self.voice_to_sample = {}
        self.voice_to_reference_audio = {}
        for v in self.voice_data:
            self.model_to_voices.setdefault(v["model"], []).append(v["person"])
            self.voice_to_sample[v["person"]] = v.get("sample", "")
            self.voice_to_reference_audio[v["person"]] = v.get("reference_audio")

        # Tk variables
        self.model_var = tk.StringVar(value=self.models[0])
        self.voice_var = tk.StringVar(value=self.model_to_voices[self.models[0]][0])
        self.rate_var = tk.StringVar(value=str(getattr(config, "TTS_RATE", 1.0)))
        self.volume_var = tk.StringVar(value=str(getattr(config, "TTS_VOLUME", 100)))
        self.sample_var = tk.StringVar(value=self.voice_to_sample.get(self.voice_var.get(), ""))
        self.page_delay_var = tk.StringVar(value="0.30")
        
        # Detect GPU availability
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            cuda_name = torch.cuda.get_device_name(0) if cuda_available else "Not available"
        except Exception:
            cuda_available = False
            cuda_name = "Error detecting"
        
        self.device_var = tk.StringVar(value="cuda" if cuda_available else "cpu")
        self.cuda_status = f"GPU ({cuda_name})" if cuda_available else "CPU (GPU not detected)"

        # Engine selection
        self.tts_engine_var = tk.StringVar(value="Coqui TTS")
        ttk.Label(self.left, text="Engine:").pack(anchor=tk.W)
        self.engine_combo = ttk.Combobox(
            self.left, textvariable=self.tts_engine_var,
            values=["Coqui TTS", "XTTS V2 Streaming", "Fast TTS (gTTS)"], state="readonly", width=35
        )
        self.engine_combo.pack(anchor=tk.W, pady=(0, 8))
        self.engine_combo.bind("<<ComboboxSelected>>", self._on_engine_changed)

        # Model selection
        ttk.Label(self.left, text="Model:").pack(anchor=tk.W)
        self.model_combo = ttk.Combobox(
            self.left,
            textvariable=self.model_var,
            values=self.models,
            state="readonly",
            width=50,
        )
        self.model_combo.pack(anchor=tk.W)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        # Voice selection (Coqui voices / reference speaker label)
        self.voice_label = ttk.Label(self.left, text="Voice / Speaker:")
        self.voice_label.pack(anchor=tk.W)

        self.voice_combo = ttk.Combobox(
            self.left,
            textvariable=self.voice_var,
            values=self.model_to_voices[self.model_var.get()],
            state="readonly",
            width=40,
        )
        self.voice_combo.pack(anchor=tk.W)
        self.voice_combo.bind("<<ComboboxSelected>>", self._on_voice_changed)

        # Sample file row + Play Sample
        row = ttk.Frame(self.left)
        row.pack(anchor=tk.W, fill=tk.X, pady=(6, 0))
        ttk.Label(row, text="Sample:").pack(side=tk.LEFT)
        self.sample_entry = ttk.Entry(row, textvariable=self.sample_var, width=45)
        self.sample_entry.pack(side=tk.LEFT, padx=(6, 6))
        self.play_btn = ttk.Button(row, text="Play Sample", command=self._play_sample)
        self.play_btn.pack(side=tk.LEFT)

        # GPU/Device selection (Coqui TTS only)
        ttk.Label(self.left, text=f"Compute Device: {self.cuda_status}").pack(anchor=tk.W, pady=(10, 6))
        device_row = ttk.Frame(self.left)
        device_row.pack(anchor=tk.W, fill=tk.X)
        self.device_combo = ttk.Combobox(
            device_row,
            textvariable=self.device_var,
            values=["cuda", "cpu"],
            state="readonly",
            width=12
        )
        self.device_combo.pack(side=tk.LEFT)
        device_note = tk.Label(device_row, text="(restart app to apply)", font=("TkDefaultFont", 8, "italic"))
        device_note.pack(side=tk.LEFT, padx=(6, 0))

        # Rate & Volume
        controls = ttk.Frame(self.left)
        controls.pack(anchor=tk.W, fill=tk.X, pady=(10, 0))

        ttk.Label(controls, text="Rate (0.5-2.0):").grid(row=0, column=0, sticky=tk.W)
        self.rate_entry = ttk.Entry(controls, textvariable=self.rate_var, width=10)
        self.rate_entry.grid(row=0, column=1, sticky=tk.W, padx=(6, 20))

        ttk.Label(controls, text="Volume (1-100):").grid(row=0, column=2, sticky=tk.W)
        self.volume_entry = ttk.Entry(controls, textvariable=self.volume_var, width=10)
        self.volume_entry.grid(row=0, column=3, sticky=tk.W, padx=(6, 0))

        # Page delay (used to smooth page turns for some engines)
        ttk.Label(controls, text="Page Delay (s):").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.page_delay_entry = ttk.Entry(controls, textvariable=self.page_delay_var, width=10)
        self.page_delay_entry.grid(row=1, column=1, sticky=tk.W, padx=(6, 0), pady=(6, 0))

        # Start/Stop buttons
        buttons = ttk.Frame(self.left)
        buttons.pack(anchor=tk.W, fill=tk.X, pady=(14, 0))
        self.start_btn = ttk.Button(buttons, text="Start", command=self.start)
        self.start_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(buttons, text="Stop", command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Page preview on the right
        ttk.Label(self.right, text="Current Page (OCR)").pack(anchor=tk.W)
        self.page_text = tk.Text(self.right, height=20, wrap=tk.WORD)
        self.page_text.pack(fill=tk.BOTH, expand=True)
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(self.right, textvariable=self.status_var).pack(anchor=tk.W, pady=(6, 0))

        # Initial UI state
        self._toggle_controls_for_engine(self.tts_engine_var.get())

    # -------------------- ORCHESTRATOR --------------------
    def start(self):
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.stop_event.clear()
        
        engine = self.tts_engine_var.get()
        if engine == "Coqui TTS":
            threading.Thread(target=self._run_coqui, daemon=True).start()
        elif engine == "Fast TTS (gTTS)":
            threading.Thread(target=self._run_realtime_tts, daemon=True).start()
        else:  # XTTS V2 Streaming
            threading.Thread(target=self._run_xtts_streaming, daemon=True).start()

    def stop(self):
        try:
            self.stop_event.set()
        except Exception:
            pass
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    # -------------------- UI helpers --------------------
    def _on_engine_changed(self, _evt=None):
        self._toggle_controls_for_engine(self.tts_engine_var.get())

    def _toggle_controls_for_engine(self, engine: str):
        # For XTTS streaming we still allow selecting the speaker (reference audio)
        # but Coqui XTTS and gTTS both use voice selections.
        is_stream = engine == "XTTS V2 Streaming"
        is_gtts = engine == "Fast TTS (gTTS)"
        # Everything stays visible, but we can relabel voice label for clarity
        if is_stream and self.model_var.get().endswith("xtts_v2"):
            self.voice_label.config(text="Reference Speaker:")
        elif is_gtts:
            self.voice_label.config(text="Language:")
        else:
            self.voice_label.config(text="Voice / Speaker:")

    def _on_model_changed(self, _evt=None):
        model = self.model_var.get()
        voices = self.model_to_voices.get(model, [])
        self.voice_combo.config(values=voices)
        if voices:
            self.voice_var.set(voices[0])
        self._on_voice_changed()

    def _on_voice_changed(self, _evt=None):
        voice = self.voice_var.get()
        self.sample_var.set(self.voice_to_sample.get(voice, ""))

    def _play_sample(self):
        path = self.sample_var.get()
        if not path:
            self.status_var.set("No sample available for this voice")
            return
        try:
            import simpleaudio as sa
            if not os.path.isabs(path):
                # resolve relative to project root
                base = os.path.dirname(os.path.dirname(__file__))
                path = os.path.join(base, path)
            wave = sa.WaveObject.from_wave_file(path)
            wave.play()
            self.status_var.set(f"Playing sample: {os.path.basename(path)}")
        except Exception as e:
            self.status_var.set(f"Sample error: {e}")

    def _run_xtts_streaming(self):
        """Run Kindle reader with XTTS streaming (no Coqui TTS needed)"""
        asyncio.set_event_loop(self.loop)
        try:
            kindle = KindleController()
            screen = ScreenCaptureService()
            ocr = OCRService(config.TESSERACT_PATH)

            # reference_audio is used as model ID for XTTS
            model_id = self.voice_to_reference_audio.get(self.voice_var.get())

            self.orchestrator = KindleReaderOrchestrator(
                tts_service=None,  # XTTS does not use TTSService
                kindle_controller=kindle,
                screen_capture=screen,
                ocr_service=ocr
            )

            self.loop.run_until_complete(
                self.orchestrator.run_with_callbacks(
                    stop_event=self.stop_event,
                    on_page_update=self._update_page,
                    on_time_update=None,
                    reference_audio=model_id,
                    xtts_streaming=True
                )
            )
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def _run_coqui(self):
        """Run Kindle reader using local Coqui TTS."""
        asyncio.set_event_loop(self.loop)
        try:
            # Build TTS service
            model = self.model_var.get()
            voice = self.voice_var.get()
            device = self.device_var.get()
            try:
                rate = float(self.rate_var.get())
            except Exception:
                rate = 1.0
            try:
                volume = int(float(self.volume_var.get()))
            except Exception:
                volume = 100

            tts = CoquiTTSService(
                model=model,
                voice=voice,
                rate=rate,
                volume=volume,
                espeak_path=getattr(config, "COQUI_ESPEAK_PATH", None),
                device=device,  # Pass explicit device selection
            )

            kindle = KindleController()
            screen = ScreenCaptureService()
            ocr = OCRService(config.TESSERACT_PATH)

            self.orchestrator = KindleReaderOrchestrator(
                tts_service=tts,
                kindle_controller=kindle,
                screen_capture=screen,
                ocr_service=ocr,
            )

            # Determine reference audio only for XTTS model in Coqui
            reference_audio = None
            if model.endswith("xtts_v2"):
                reference_audio = self.voice_to_reference_audio.get(voice)

            self.loop.run_until_complete(
                self.orchestrator.run_with_callbacks(
                    stop_event=self.stop_event,
                    on_page_update=self._update_page,
                    on_time_update=self._on_time_update,
                    reference_audio=reference_audio,
                    xtts_streaming=False,
                )
            )
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def _run_realtime_tts(self):
        """Run Kindle reader using gTTS for fast text-to-speech."""
        asyncio.set_event_loop(self.loop)
        try:
            # Build gTTS service
            # For gTTS, model_name is the language code (e.g., "en", "es", "fr")
            model = self.model_var.get() if self.model_var.get() in ["en", "es", "fr", "de"] else "en"
            try:
                rate = float(self.rate_var.get())
            except Exception:
                rate = 1.0
            try:
                volume = int(float(self.volume_var.get()))
            except Exception:
                volume = 100

            # For gTTS, we use language code as model_name
            tts = RealTimeTTSService(
                model_name=model,
                speaker=None,  # gTTS doesn't use speaker IDs
                rate=rate,
                volume=volume,
                device=self.device_var.get(),
            )

            kindle = KindleController()
            screen = ScreenCaptureService()
            ocr = OCRService(config.TESSERACT_PATH)

            self.orchestrator = KindleReaderOrchestrator(
                tts_service=tts,
                kindle_controller=kindle,
                screen_capture=screen,
                ocr_service=ocr,
            )

            self.loop.run_until_complete(
                self.orchestrator.run_with_callbacks(
                    stop_event=self.stop_event,
                    on_page_update=self._update_page,
                    on_time_update=self._on_time_update,
                    reference_audio=None,
                    xtts_streaming=False,
                )
            )
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    # -------------------- callbacks --------------------
    def _update_page(self, text: str):
        def _ui():
            self.page_text.delete("1.0", tk.END)
            self.page_text.insert("1.0", text)
        try:
            self.root.after(0, _ui)
        except Exception:
            pass

    def _on_time_update(self, duration: float):
        try:
            self.status_var.set(f"Estimated duration: {duration:.1f}s")
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = KindleTTSApp(root)
    root.mainloop()

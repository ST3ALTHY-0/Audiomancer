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
from controllers.WindowController import WindowController
from services.saveUserConfig import ConfigManager, create_config_from_gui, apply_config_to_gui
import config
from services.tts_xtts_client import stream_tts, play_stream

class KindleTTSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TTS Reader")
        self.root.geometry("1000x800")
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
        
        # Configuration manager
        self.config_manager = ConfigManager()

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
        
        # gTTS language options and XTTS-only model list
        self.gtts_languages = ["en", "es", "fr", "de"]
        self.xtts_models = sorted([m for m in self.models if m.endswith("xtts_v2")]) or ["tts_models/multilingual/multi-dataset/xtts_v2"]

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
        self.sample_row = ttk.Frame(self.left)
        self.sample_row.pack(anchor=tk.W, fill=tk.X, pady=(6, 0))
        ttk.Label(self.sample_row, text="Sample:").pack(side=tk.LEFT)
        self.sample_entry = ttk.Entry(self.sample_row, textvariable=self.sample_var, width=45)
        self.sample_entry.pack(side=tk.LEFT, padx=(6, 6))
        self.play_btn = ttk.Button(self.sample_row, text="Play Sample", command=self._play_sample)
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

        # Window selection
        window_frame = ttk.Frame(self.left)
        window_frame.pack(anchor=tk.W, fill=tk.X, pady=(14, 0))
        ttk.Label(window_frame, text="Target Window:").pack(anchor=tk.W)
        
        window_select_row = ttk.Frame(window_frame)
        window_select_row.pack(anchor=tk.W, fill=tk.X, pady=(4, 0))
        
        self.selected_window_var = tk.StringVar(value="")
        self.window_combo = ttk.Combobox(
            window_select_row,
            textvariable=self.selected_window_var,
            values=[],
            state="readonly",
            width=50
        )
        self.window_combo.pack(side=tk.LEFT, padx=(0, 6))
        
        self.refresh_windows_btn = ttk.Button(
            window_select_row,
            text="Refresh Windows",
            command=self._refresh_windows
        )
        self.refresh_windows_btn.pack(side=tk.LEFT)

        # Configuration Management Section
        config_frame = ttk.LabelFrame(self.left, text="Configuration Profiles", padding=10)
        config_frame.pack(anchor=tk.W, fill=tk.X, pady=(14, 0))
        
        # Row 1: Save config
        save_row = ttk.Frame(config_frame)
        save_row.pack(anchor=tk.W, fill=tk.X)
        ttk.Label(save_row, text="Profile Name:").pack(side=tk.LEFT)
        self.config_name_var = tk.StringVar()
        self.config_name_entry = ttk.Entry(save_row, textvariable=self.config_name_var, width=20)
        self.config_name_entry.pack(side=tk.LEFT, padx=(6, 6))
        self.save_config_btn = ttk.Button(save_row, text="Save Profile", command=self._save_config)
        self.save_config_btn.pack(side=tk.LEFT)
        
        # Row 2: Load config
        load_row = ttk.Frame(config_frame)
        load_row.pack(anchor=tk.W, fill=tk.X, pady=(8, 0))
        ttk.Label(load_row, text="Load Profile:").pack(side=tk.LEFT)
        self.load_config_var = tk.StringVar()
        self.load_config_combo = ttk.Combobox(
            load_row,
            textvariable=self.load_config_var,
            values=[],
            state="readonly",
            width=18
        )
        self.load_config_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.load_config_btn = ttk.Button(load_row, text="Load", command=self._load_config)
        self.load_config_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.delete_config_btn = ttk.Button(load_row, text="Delete", command=self._delete_config)
        self.delete_config_btn.pack(side=tk.LEFT)
        
        # Row 3: Auto-load
        auto_row = ttk.Frame(config_frame)
        auto_row.pack(anchor=tk.W, fill=tk.X, pady=(8, 0))
        self.auto_load_btn = ttk.Button(auto_row, text="Set as Auto-Load", command=self._set_auto_load)
        self.auto_load_btn.pack(side=tk.LEFT)
        self.clear_auto_load_btn = ttk.Button(auto_row, text="Clear Auto-Load", command=self._clear_auto_load)
        self.clear_auto_load_btn.pack(side=tk.LEFT, padx=(4, 0))
        
        # Auto-load status label
        self.auto_load_status_var = tk.StringVar()
        ttk.Label(config_frame, textvariable=self.auto_load_status_var, font=("TkDefaultFont", 8, "italic")).pack(anchor=tk.W, pady=(4, 0))

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
        self._refresh_windows()
        self._refresh_config_list()
        self._update_auto_load_status()
        
        # Auto-load configuration if set
        self._auto_load_config()

    # -------------------- ORCHESTRATOR --------------------
    def _refresh_windows(self):
        """Refresh the list of available windows"""
        try:
            controller = WindowController()
            windows = controller.get_all_windows()
            self.window_combo.config(values=windows)
            
            # Try to find and select Kindle for PC by default
            for window in windows:
                if "Kindle for PC" in window:
                    self.selected_window_var.set(window)
                    break
            
            # If no window is selected yet and there are windows, select the first one
            if not self.selected_window_var.get() and windows:
                self.selected_window_var.set(windows[0])
                
            self.status_var.set(f"Found {len(windows)} windows")
        except Exception as e:
            self.status_var.set(f"Error refreshing windows: {e}")
    
    # -------------------- CONFIG MANAGEMENT --------------------
    def _refresh_config_list(self):
        """Refresh the list of saved configurations"""
        configs = self.config_manager.list_configs()
        self.load_config_combo.config(values=configs)
        if configs and not self.load_config_var.get():
            self.load_config_var.set(configs[0])
    
    def _save_config(self):
        """Save current settings as a new configuration profile"""
        config_name = self.config_name_var.get().strip()
        if not config_name:
            self.status_var.set("Please enter a profile name")
            return
        
        # Get current settings
        config_data = create_config_from_gui(self)
        
        # Save to file
        if self.config_manager.save_config(config_name, config_data):
            self.status_var.set(f"Profile '{config_name}' saved successfully")
            self.config_name_var.set("")  # Clear the input
            self._refresh_config_list()
        else:
            self.status_var.set(f"Failed to save profile '{config_name}'")
    
    def _load_config(self):
        """Load a saved configuration profile"""
        config_name = self.load_config_var.get()
        if not config_name:
            self.status_var.set("Please select a profile to load")
            return
        
        config_data = self.config_manager.load_config(config_name)
        if config_data:
            apply_config_to_gui(self, config_data)
            self.status_var.set(f"Profile '{config_name}' loaded successfully")
        else:
            self.status_var.set(f"Failed to load profile '{config_name}'")
    
    def _delete_config(self):
        """Delete a saved configuration profile"""
        config_name = self.load_config_var.get()
        if not config_name:
            self.status_var.set("Please select a profile to delete")
            return
        
        # Confirm deletion
        import tkinter.messagebox as messagebox
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete profile '{config_name}'?"):
            if self.config_manager.delete_config(config_name):
                self.status_var.set(f"Profile '{config_name}' deleted")
                self._refresh_config_list()
                self._update_auto_load_status()
            else:
                self.status_var.set(f"Failed to delete profile '{config_name}'")
    
    def _set_auto_load(self):
        """Set the selected configuration to auto-load on startup"""
        config_name = self.load_config_var.get()
        if not config_name:
            self.status_var.set("Please select a profile to set as auto-load")
            return
        
        if self.config_manager.set_auto_load(config_name):
            self.status_var.set(f"Profile '{config_name}' will auto-load on startup")
            self._update_auto_load_status()
        else:
            self.status_var.set(f"Failed to set auto-load for '{config_name}'")
    
    def _clear_auto_load(self):
        """Clear the auto-load configuration"""
        if self.config_manager.set_auto_load(None):
            self.status_var.set("Auto-load cleared")
            self._update_auto_load_status()
        else:
            self.status_var.set("Failed to clear auto-load")
    
    def _update_auto_load_status(self):
        """Update the auto-load status label"""
        auto_load = self.config_manager.get_auto_load()
        if auto_load:
            self.auto_load_status_var.set(f"Auto-load: {auto_load}")
        else:
            self.auto_load_status_var.set("Auto-load: None")
    
    def _auto_load_config(self):
        """Auto-load configuration on startup if set"""
        config_data = self.config_manager.get_auto_load_config()
        if config_data:
            apply_config_to_gui(self, config_data)
            auto_load_name = self.config_manager.get_auto_load()
            self.status_var.set(f"Auto-loaded profile: {auto_load_name}")
    
    # -------------------- ORCHESTRATOR --------------------
    
    def start(self):
        # Validate window selection
        if not self.selected_window_var.get():
            self.status_var.set("Please select a target window")
            return
            
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
        engine = self.tts_engine_var.get()
        if engine == "Fast TTS (gTTS)":
            # Show languages as models; disable voice selection and sample controls
            self.model_combo.config(values=self.gtts_languages, state="readonly")
            self.model_var.set(self.gtts_languages[0])
            self.voice_combo.config(values=[], state="disabled")
            self.voice_var.set("")
            self.sample_entry.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.voice_label.config(text="Language:")
        elif engine == "XTTS V2 Streaming":
            # Restrict to XTTS models, enable voices mapped to XTTS
            self.model_combo.config(values=self.xtts_models, state="readonly")
            self.model_var.set(self.xtts_models[0])
            voices = self.model_to_voices.get(self.model_var.get(), [])
            self.voice_combo.config(values=voices, state="readonly")
            if voices:
                self.voice_var.set(voices[0])
            # Sample preview allowed but read-only
            self.sample_entry.config(state="readonly")
            self.play_btn.config(state="normal")
            self.voice_label.config(text="Reference Speaker:")
        else:
            # Coqui: show all models and voices
            self.model_combo.config(values=self.models, state="readonly")
            voices = self.model_to_voices.get(self.model_var.get(), [])
            self.voice_combo.config(values=voices, state="readonly")
            if voices and not self.voice_var.get():
                self.voice_var.set(voices[0])
            # Update sample controls based on specific model
            self._on_model_changed()

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
        # Adjust sample controls depending on model/engine
        is_xtts = model.endswith("xtts_v2")
        is_vits = "vits" in model.lower()
        if self.tts_engine_var.get() == "Fast TTS (gTTS)":
            self.sample_entry.config(state="disabled")
            self.play_btn.config(state="disabled")
        elif is_xtts:
            self.sample_entry.config(state="readonly")
            self.play_btn.config(state="normal")
            self.voice_label.config(text="Reference Speaker:")
        elif is_vits:
            # VITS does not accept reference audio; keep sample path read-only
            self.sample_entry.config(state="readonly")
            self.play_btn.config(state="normal")
            self.voice_label.config(text="Voice / Speaker:")
        else:
            self.sample_entry.config(state="readonly")
            self.play_btn.config(state="normal")

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
        """Run reader with XTTS streaming (no Coqui TTS needed)"""
        asyncio.set_event_loop(self.loop)
        try:
            window_controller = WindowController()
            if not window_controller.find_window(self.selected_window_var.get()):
                self.status_var.set(f"Window not found: {self.selected_window_var.get()}")
                return
            
            screen = ScreenCaptureService()
            ocr = OCRService(config.TESSERACT_PATH)

            # reference_audio is used as model ID for XTTS
            model_id = self.voice_to_reference_audio.get(self.voice_var.get())

            self.orchestrator = KindleReaderOrchestrator(
                tts_service=None,  # XTTS does not use TTSService
                kindle_controller=window_controller,
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
        """Run reader using local Coqui TTS."""
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

            window_controller = WindowController()
            if not window_controller.find_window(self.selected_window_var.get()):
                self.status_var.set(f"Window not found: {self.selected_window_var.get()}")
                return
            
            screen = ScreenCaptureService()
            ocr = OCRService(config.TESSERACT_PATH)

            self.orchestrator = KindleReaderOrchestrator(
                tts_service=tts,
                kindle_controller=window_controller,
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
        """Run reader using gTTS for fast text-to-speech."""
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

            window_controller = WindowController()
            if not window_controller.find_window(self.selected_window_var.get()):
                self.status_var.set(f"Window not found: {self.selected_window_var.get()}")
                return
            
            screen = ScreenCaptureService()
            ocr = OCRService(config.TESSERACT_PATH)

            self.orchestrator = KindleReaderOrchestrator(
                tts_service=tts,
                kindle_controller=window_controller,
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

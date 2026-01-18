import asyncio
import os
import torch
import simpleaudio as sa
from TTS.api import TTS
from .tts_service import TTSService
from typing import Optional
import soundfile as sf
import numpy as np
import librosa
import threading


class CoquiTTSService(TTSService):
    """Coqui TTS implementation with pipelined audio generation and non-blocking playback"""

    # -------------------- runtime setters --------------------

    def set_model(self, model: str):
        self.model_name = model
        self._tts_engine = None

        if model == "tts_models/multilingual/multi-dataset/xtts_v2":
            try:
                from TTS.tts.configs.xtts_config import XttsConfig
                from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
                from TTS.config.shared_configs import BaseDatasetConfig, BaseAudioConfig
                torch.serialization.add_safe_globals([
                    XttsConfig,
                    XttsAudioConfig,
                    XttsArgs,
                    BaseDatasetConfig,
                    BaseAudioConfig,
                ])
            except Exception as e:
                print(f"XTTS safe globals error: {e}")

    def set_volume(self, volume: int):
        self.volume = max(1, min(100, volume))

    def set_rate(self, rate: float):
        self.rate = max(0.5, min(2.0, rate))

    def set_voice(self, voice: str):
        self.voice = voice

    # -------------------- init --------------------

    def __init__(
        self,
        model: str = "tts_models/en/vctk/vits",
        voice: Optional[str] = "p254",
        rate: float = 1.0,
        volume: int = 100,
        espeak_path: Optional[str] = None,
        page_turn_buffer: float = 0.3,
        device: Optional[str] = None,  # "cuda" or "cpu"; None = auto-detect
    ):
        self.model_name = model
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.page_turn_buffer = max(0.0, min(1.0, page_turn_buffer))

        self._tts_engine = None

        # Device selection with better detection
        if device:
            self._device = device  # Use explicit override if provided
        else:
            # Auto-detect GPU
            if torch.cuda.is_available():
                self._device = "cuda"
                print(f"CUDA available: {torch.cuda.get_device_name(0)}")
            else:
                self._device = "cpu"
                print("CUDA not detected, using CPU (slower)")
                print(f"  PyTorch CUDA available: {torch.cuda.is_available()}")
                print(f"  PyTorch CUDA version: {torch.version.cuda}")
                
        #TODO: make this a var user can control
        os.makedirs("output/temp", exist_ok=True)
        self._current_file = "output/temp/temp_speech_current.wav"
        self._next_file = "output/temp/temp_speech_next.wav"
        self._prefetch_file = "output/temp/temp_speech_prefetch.wav"
        self._prefetched_text: Optional[str] = None
        self._prefetch_ready: bool = False
        self._prefetch_task: Optional[asyncio.Task] = None
        self._playback_thread = None  # Track background playback thread
        self._playback_obj = None  # Track active playback object

        if espeak_path:
            os.environ["PHONEMIZER_ESPEAK_PATH"] = espeak_path

    async def initialize(self) -> None:
        # Ensure XTTS safe globals are set before loading model
        if self.model_name == "tts_models/multilingual/multi-dataset/xtts_v2":
            try:
                from TTS.tts.configs.xtts_config import XttsConfig
                from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
                from TTS.config.shared_configs import BaseDatasetConfig, BaseAudioConfig
                torch.serialization.add_safe_globals([
                    XttsConfig,
                    XttsAudioConfig,
                    XttsArgs,
                    BaseDatasetConfig,
                    BaseAudioConfig,
                ])
            except Exception as e:
                print(f"XTTS safe globals error: {e}")

        # Double-check device is actually available (CPU torch can't use cuda)
        if self._device == "cuda" and not torch.cuda.is_available():
            print(f"Warning: CUDA requested but not available, falling back to CPU")
            self._device = "cpu"

        try:
            self._tts_engine = TTS(self.model_name).to(self._device)
            print(f"Coqui TTS initialized on {self._device}")
        except Exception as e:
            print(f"Error initializing TTS on {self._device}: {e}")
            if self._device == "cuda":
                print("Falling back to CPU...")
                self._device = "cpu"
                self._tts_engine = TTS(self.model_name).to(self._device)
                print(f"Coqui TTS initialized on {self._device}")
            else:
                raise

    # -------------------- core audio generation --------------------

    async def generate_audio(
        self,
        text: str,
        file_path: str,
        reference_audio: Optional[str] = None,
    ) -> float:
        if not self._tts_engine:
            raise RuntimeError("TTS engine not initialized")

        safe_text = text.replace("\n", " ").replace("\r", " ")

        # Expand contractions for VITS model to improve pronunciation
        if "vits" in self.model_name.lower():
            safe_text = self._expand_contractions(safe_text)

        if self.model_name == "tts_models/multilingual/multi-dataset/xtts_v2":
            if not reference_audio:
                raise ValueError("XTTS requires reference_audio")

            await asyncio.to_thread(
                self._tts_engine.tts_to_file,
                text=safe_text,
                speaker_wav=reference_audio,
                language="en",
                file_path=file_path,
            )
        else:
            await asyncio.to_thread(
                self._tts_engine.tts_to_file,
                text=safe_text,
                speaker=self.voice,
                file_path=file_path,
            )

        audio, sr = sf.read(file_path)

        # volume
        audio = np.clip(audio * (self.volume / 100), -1.0, 1.0)

        # speed (pitch preserved)
        if self.rate != 1.0:
            mono = audio.mean(axis=1) if audio.ndim > 1 else audio
            stretched = librosa.effects.time_stretch(
                mono.astype(np.float32), rate=self.rate
            )
            audio = (
                np.stack([stretched, stretched], axis=1)
                if audio.ndim > 1
                else stretched
            )

        sf.write(file_path, audio, sr)
        return len(audio) / sr

    def estimate_duration(self, file_path: str) -> float:
        info = sf.info(file_path)
        return info.frames / info.samplerate

    def _expand_contractions(self, text: str) -> str:
        """Expand contractions to improve VITS pronunciation"""
        import re

        # Normalize ALL apostrophe-like characters to straight ASCII apostrophe
        apostrophe_variants = [
            ''',  # U+2019 right single quotation mark
            ''',  # U+2018 left single quotation mark
            'ʼ',  # U+02BC modifier letter apostrophe
            '‛',  # U+201B single high-reversed-9
            '`',  # U+0060 grave accent (sometimes used)
            '´',  # U+00B4 acute accent (sometimes used)
            '\u2019',  # Explicit unicode for right single quote
            '\u2018',  # Explicit unicode for left single quote
        ]
        for variant in apostrophe_variants:
            text = text.replace(variant, "'")

        # Specific common contractions with word boundaries
        contractions_dict = {
            "ain't": "am not",
            "aren't": "are not",
            "can't": "cannot",
            "can't've": "cannot have",
            "could've": "could have",
            "couldn't": "could not",
            "didn't": "did not",
            "doesn't": "does not",
            "don't": "do not",
            "hadn't": "had not",
            "hasn't": "has not",
            "haven't": "have not",
            "he'd": "he would",
            "he'll": "he will",
            "he's": "he is",
            "she'd": "she would",
            "she'll": "she will",
            "she's": "she is",
            "how'd": "how did",
            "how'll": "how will",
            "how's": "how is",
            "i'd": "i would",
            "i'll": "i will",
            "i'm": "i am",
            "i've": "i have",
            "isn't": "is not",
            "it'd": "it would",
            "it'll": "it will",
            "it's": "it is",
            "let's": "let us",
            "shouldn't": "should not",
            "that's": "that is",
            "there's": "there is",
            "they'd": "they would",
            "they'll": "they will",
            "they're": "they are",
            "they've": "they have",
            "wasn't": "was not",
            "we'd": "we would",
            "we'll": "we will",
            "we're": "we are",
            "we've": "we have",
            "weren't": "were not",
            "what's": "what is",
            "won't": "will not",
            "wouldn't": "would not",
            "you'd": "you would",
            "you'll": "you will",
            "you're": "you are",
            "you've": "you have",
            "should've": "should have",
            "would've": "would have",
            "might've": "might have",
            "must've": "must have",
            "mightn't": "might not",
            "mustn't": "must not",
            "y'all": "you all",
            "y'all'd": "you all would",
            "y'all're": "you all are",
            "y'all've": "you all have",
            "o'clock": "of the clock",
            "ma'am": "madam",
            "y'know": "you know",
            "c'mon": "come on",

        }

        # Replace specific contractions with word boundaries
        pattern = re.compile(r"\b(" + "|".join(re.escape(k)
                             for k in contractions_dict.keys()) + r")\b", re.IGNORECASE)
        result = pattern.sub(
            lambda m: contractions_dict[m.group(0).lower()], text)

        # Handle 's contractions in correct order: HAS → IS → POSSESSIVE
        
        result = re.sub(
            r"\b(he|she|it|that|there|who|what|where|when|why|how)'s\s+"
            r"(gone|been|done|had|made|seen|known|taken|given|eaten|written|spoken|broken|fallen|risen|driven|thrown|shown|grown|flown|drawn|worn|torn|born|sworn|chosen|frozen|stolen|forgotten|hidden|ridden|bitten|\w+ed)\b",
            r"\1 has \2",
            result,
            flags=re.IGNORECASE
        )
        
        result = re.sub(
            r"\b(he|she|it|that|there|here|who|what|where|when|why|how)'s\b",
            r"\1 is",
            result,
            flags=re.IGNORECASE
        )
        
        result = re.sub(r"(\w+)'s\b", lambda m: m.group(1) + "s", result)

        # General patterns for other contractions
        result = re.sub(r"(\w+)'re\b", lambda m: m.group(1) + " are", result)
        result = re.sub(r"(\w+)'ve\b", lambda m: m.group(1) + " have", result)
        result = re.sub(r"(\w+)'ll\b", lambda m: m.group(1) + " will", result)
        result = re.sub(r"(\w+)'d\b", lambda m: m.group(1) + " would", result)
        result = re.sub(r"(\w+)n't\b", lambda m: m.group(1) + " not", result)
        result = re.sub(r"(\w+)'m\b", lambda m: m.group(1) + " am", result)

        return result

    # -------------------- playback --------------------

    def _play_blocking(self, file_path: str) -> None:
        """Play audio file in a blocking manner (used in thread)"""
        try:
            wave = sa.WaveObject.from_wave_file(file_path)
            self._playback_obj = wave.play()
            self._playback_obj.wait_done()
        except Exception as e:
            print(f"Playback error: {e}")

    async def speak_file_blocking(self, file_path: str) -> None:
        """Play audio file and wait for completion (blocking)"""
        wave = sa.WaveObject.from_wave_file(file_path)
        await asyncio.to_thread(wave.play().wait_done)

    async def speak_file_nonblocking(self, file_path: str) -> float:
        """
        Start playing audio file without blocking.
        Returns the audio duration so orchestrator knows when it will finish.
        """
        try:
            duration = self.estimate_duration(file_path)
            # Start playback in background thread
            self._playback_thread = threading.Thread(
                target=self._play_blocking, args=(file_path,), daemon=True
            )
            self._playback_thread.start()
            return duration
        except Exception as e:
            print(f"Error starting playback: {e}")
            return 0.0

    async def wait_for_playback(self) -> None:
        """Wait for current playback to finish"""
        if self._playback_thread:
            await asyncio.to_thread(self._playback_thread.join)

    # -------------------- pipelined speak --------------------

    async def speak(
        self,
        text: str,
        next_text: Optional[str] = None,
        reference_audio: Optional[str] = None,
    ) -> tuple:
        """
        Non-blocking pipelined playback: generates, starts playback immediately,
        and returns control without waiting for audio to finish.

        Prefetches the *next* page audio near the end of current playback so it is
        ready when the next page starts, avoiding overlapping audio.

        Returns: (duration, page_turn_delay) where duration is audio length
        and page_turn_delay can be used for page-turning timing.
        """

        # If we already prefetched this exact text, reuse it instead of regenerating
        if self._prefetch_ready and self._prefetched_text == text:
            duration = self.estimate_duration(self._prefetch_file)
            await self.speak_file_nonblocking(self._prefetch_file)
            # Clear prefetch state
            self._prefetch_ready = False
            self._prefetched_text = None
            # Kick off prefetch for the following page if provided
            if next_text:
                self._schedule_prefetch(next_text, reference_audio, duration)
            page_turn_delay = duration * (1 - self.page_turn_buffer)
            return duration, page_turn_delay

        # Generate current page audio
        duration = await self.generate_audio(
            text, self._current_file, reference_audio
        )

        # Start playing current audio WITHOUT BLOCKING
        # Returns immediately so orchestrator can turn page ASAP
        await self.speak_file_nonblocking(self._current_file)

        # Schedule prefetch of next page near the end of current playback
        if next_text:
            self._schedule_prefetch(next_text, reference_audio, duration)

        page_turn_delay = duration * (1 - self.page_turn_buffer)
        return duration, page_turn_delay

    def _schedule_prefetch(self, next_text: str, reference_audio: Optional[str], duration: float, preload_ratio: float = 0.7):
        """Schedule prefetch of next page audio after a portion of current playback.
        preload_ratio defines when to start prefetching (e.g., 0.7 = 70% through)."""
        async def _prefetch_job():
            try:
                await asyncio.sleep(max(0.0, duration * preload_ratio))
                await self.generate_audio(next_text, self._prefetch_file, reference_audio)
                self._prefetched_text = next_text
                self._prefetch_ready = True
            except Exception as e:
                print(f"Prefetch error: {e}")
                self._prefetch_ready = False
                self._prefetched_text = None

        # Cancel any existing prefetch task to avoid overlap
        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()
        self._prefetch_task = asyncio.create_task(_prefetch_job())

    async def prefetch_next(self, next_text: str, reference_audio: Optional[str] = None):
        """Immediately start generating audio for next page (called after OCR)."""
        async def _prefetch_job():
            try:
                await self.generate_audio(next_text, self._prefetch_file, reference_audio)
                self._prefetched_text = next_text
                self._prefetch_ready = True
                print(
                    f"[DEBUG] Prefetch completed for next page ({len(next_text)} chars)")
            except Exception as e:
                print(f"Prefetch error: {e}")
                self._prefetch_ready = False
                self._prefetched_text = None

        # Cancel any existing prefetch task to avoid overlap
        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()
        self._prefetch_task = asyncio.create_task(_prefetch_job())

    # -------------------- cleanup --------------------

    async def cleanup(self) -> None:
        self._tts_engine = None
        for f in (self._current_file, self._next_file, self._prefetch_file):
            try:
                os.remove(f)
            except FileNotFoundError:
                pass

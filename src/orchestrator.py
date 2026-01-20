import asyncio
from typing import Optional, Tuple
from services.tts_service import TTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.WindowController import WindowController
import config
from services.tts_xtts_client import stream_tts, play_stream
import threading


class KindleReaderOrchestrator:
    """Coordinates OCR + Window Control + TTS playback with optional XTTS streaming."""

    def __init__(
        self,
        tts_service: Optional[TTSService],
        kindle_controller: WindowController,
        screen_capture: ScreenCaptureService,
        ocr_service: OCRService,
        crop_settings: Optional[Tuple[int, int, int, int]] = None,
        page_delay_seconds: Optional[float] = None,
    ):
        self.tts = tts_service
        self.kindle = kindle_controller
        self.screen_capture = screen_capture
        self.ocr = ocr_service
        self.crop_settings = crop_settings or self._load_crop_settings_from_config()
        # User-controlled turn timing: fraction of audio duration to wait before turning page
        # E.g., 0.72 = turn at 72% of audio playback (allows overlap)
        try:
            self.page_turn_timing = max(0.0, min(1.0, float(page_delay_seconds))) if page_delay_seconds is not None else 0.72
        except Exception:
            self.page_turn_timing = 0.72  # Default to 72%

    def _load_crop_settings_from_config(self) -> Tuple[int, int, int, int]:
        return (
            config.CROP_LEFT,
            config.CROP_TOP,
            config.CROP_RIGHT,
            config.CROP_BOTTOM,
        )

    async def initialize(self):
        """Initialize TTS service and verify target window is available."""
        if self.tts:
            await self.tts.initialize()
        if not self.kindle.is_valid():
            raise RuntimeError("Target window not found or no longer valid")

    async def read_current_page(self) -> Optional[str]:
        """Capture current page screenshot and extract text via OCR."""
        if not self.kindle.is_valid():
            raise RuntimeError("Kindle window no longer valid")

        screenshot = self.screen_capture.capture_window(
            self.kindle.hwnd,
            crop=self.crop_settings,
        )

        if not screenshot:
            return None

        text = await self.ocr.extract_text(screenshot)
        return text.strip() if text else None

    async def _play_xtts_streaming(self, text: str):
        """Play text using XTTS streaming in a separate thread."""
        def stream_job():
            audio_stream = stream_tts(text)
            play_stream(audio_stream)

        threading.Thread(target=stream_job, daemon=True).start()
        await asyncio.sleep(0.5)  # Brief wait for stream to start

    async def _play_tts_service(
        self,
        current_text: str,
        next_text: Optional[str],
        reference_audio: Optional[str],
        on_time_update
    ) -> Tuple[float, Optional[asyncio.Task]]:
        """Play text using TTS service and return duration and playback task."""
        duration, _ = await self.tts.speak(
            current_text,
            next_text=next_text,
            reference_audio=reference_audio,
        )
        playback_task = asyncio.create_task(self.tts.wait_for_playback())

        print(
            f"[DEBUG] Duration: {duration:.2f}s, {len(current_text)} chars, {len(current_text.split())} words")

        if on_time_update:
            on_time_update(duration)

        return duration, playback_task

    async def run_with_callbacks(
        self,
        stop_event: asyncio.Event,
        on_page_update=None,
        on_time_update=None,
        reference_audio=None,
        xtts_streaming=False
    ):
        """Run the reader with UI callbacks. Supports both TTS service and XTTS streaming."""
        await self.initialize()

        # Read first page
        current_text = await self.read_current_page()
        if not current_text:
            return

        if on_page_update:
            on_page_update(current_text)

        last_text = None
        next_text = None

        while not stop_event.is_set():
            try:
                # Play current page audio
                playback_task = None
                duration = 0.0

                if xtts_streaming:
                    await self._play_xtts_streaming(current_text)
                    duration = 0.5  # Placeholder duration
                elif self.tts:
                    duration, playback_task = await self._play_tts_service(
                        current_text, next_text, reference_audio, on_time_update
                    )

                # Turn page at user-specified fraction of audio duration
                # This allows the page turn to happen during playback for smoother transitions
                turn_delay = max(0.1, duration * self.page_turn_timing) if duration else 0.3
                await asyncio.sleep(turn_delay)

                self.kindle.turn_page()
                await asyncio.sleep(0.2)  # Brief delay for page to render

                # Read next page
                next_text = await self.read_current_page()
                if next_text == last_text:
                    next_text = None

                # Update UI with new page
                if on_page_update and next_text:
                    on_page_update(next_text)

                # Prefetch audio for next page while current audio finishes
                if self.tts and next_text:
                    await self.tts.prefetch_next(next_text, reference_audio)
                    print("[DEBUG] Prefetch started for next page")

                # Wait for current playback to finish
                if playback_task:
                    try:
                        await playback_task
                    except Exception as e:
                        print(f"Playback wait error: {e}")

                # Move to next page
                last_text = current_text
                current_text = next_text

                if not current_text:
                    await asyncio.sleep(0.5)

            except Exception as e:
                print(f"Reader error: {e}")
                await asyncio.sleep(1)

        if self.tts:
            await self.tts.cleanup()

    async def run(self, stop_event: asyncio.Event):
        """Simplified run without callbacks (TTS service only)."""
        await self.initialize()

        current_text = await self.read_current_page()
        if not current_text:
            return

        while not stop_event.is_set():
            try:
                self.kindle.turn_page()
                await asyncio.sleep(0.2)  # Brief delay for page to render
                next_text = await self.read_current_page()

                if self.tts:
                    await self.tts.speak(current_text, next_text=next_text)

                current_text = next_text

            except Exception as e:
                print(f"Reader error: {e}")
                await asyncio.sleep(1)

        if self.tts:
            await self.tts.cleanup()

import asyncio
from typing import Optional, Tuple
from services.tts_service import TTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.kindle_controller import KindleController
import config
from xtts_client import stream_tts, play_stream
import threading


class KindleReaderOrchestrator:
    """Coordinates OCR + Kindle + pipelined TTS.
       Supports optional TTS for XTTS streaming."""

    def __init__(
        self,
        tts_service: Optional[TTSService],  # Optional for XTTS streaming
        kindle_controller: KindleController,
        screen_capture: ScreenCaptureService,
        ocr_service: OCRService,
        crop_settings: Optional[Tuple[int, int, int, int]] = None
    ):
        self.tts = tts_service
        self.kindle = kindle_controller
        self.screen_capture = screen_capture
        self.ocr = ocr_service
        self.crop_settings = crop_settings or self._load_crop_settings_from_config()

    def _load_crop_settings_from_config(self) -> Tuple[int, int, int, int]:
        return (
            config.CROP_LEFT,
            config.CROP_TOP,
            config.CROP_RIGHT,
            config.CROP_BOTTOM,
        )

    async def initialize(self):
        """Initialize TTS if exists, and check Kindle window"""
        if self.tts:
            await self.tts.initialize()
        if not self.kindle.find_window():
            raise RuntimeError("Kindle window not found")

    async def read_current_page(self) -> Optional[str]:
        """Capture current page and extract text"""
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

    # ------------------------------------------------------------------

    async def run_with_callbacks(
        self,
        stop_event: asyncio.Event,
        on_page_update=None,
        on_time_update=None,
        reference_audio=None,
        xtts_streaming=False
    ):
        """Run the reader with callbacks. Supports XTTS streaming if requested."""
        await self.initialize()
        last_text = None

        # Prime the first page
        current_text = await self.read_current_page()
        if not current_text:
            return

        if on_page_update:
            on_page_update(current_text)

        # Lookahead buffer (text of next page) for prefetching audio
        next_text = None

        while not stop_event.is_set():
            try:
                # Speak current page first
                playback_task = None
                duration = 0.0
                if xtts_streaming:
                    def stream_job(text_to_read=current_text, model_id=reference_audio):
                        audio_stream = stream_tts(text_to_read, model_id)
                        play_stream(audio_stream)
                    threading.Thread(target=stream_job, daemon=True).start()
                    await asyncio.sleep(0.5)
                    duration = 0.5  # rough placeholder for xtts streaming
                elif self.tts:
                    duration, _ = await self.tts.speak(
                        current_text,
                        next_text=next_text,
                        reference_audio=reference_audio,
                    )
                    playback_task = asyncio.create_task(self.tts.wait_for_playback())
                    print(f"[DEBUG] Page duration: {duration:.2f}s, text length: {len(current_text)} chars, {len(current_text.split())} words")
                    if on_time_update:
                        on_time_update(duration)

                # Turn page near the end of current playback to preprocess next page
                if duration:
                    turn_delay = max(0.1, duration * 0.72)  # flip around 70-80%
                    await asyncio.sleep(turn_delay)
                else:
                    await asyncio.sleep(0.3)

                self.kindle.turn_page()
                await asyncio.sleep(0.2)

                next_text = await self.read_current_page()
                if next_text == last_text:
                    next_text = None

                # Update UI with new page while remaining audio finishes
                if on_page_update and next_text:
                    on_page_update(next_text)

                # Immediately start generating next audio while current audio finishes
                if self.tts and next_text:
                    await self.tts.prefetch_next(next_text, reference_audio)
                    print(f"[DEBUG] Triggered immediate prefetch for next page")

                # Ensure playback fully finished before starting next loop
                if playback_task:
                    try:
                        await playback_task
                    except Exception as e:
                        print(f"Playback wait error: {e}")

                last_text = current_text
                current_text = next_text

                if not current_text:
                    await asyncio.sleep(0.5)

            except Exception as e:
                print(f"Reader error: {e}")
                await asyncio.sleep(1)

        if self.tts:
            await self.tts.cleanup()

    # ------------------------------------------------------------------

    async def run(self, stop_event: asyncio.Event):
        """Simpler run without callbacks (TTS only)"""
        await self.initialize()

        current_text = await self.read_current_page()
        if not current_text:
            return

        while not stop_event.is_set():
            try:
                self.kindle.turn_page()
                await asyncio.sleep(0.2)
                next_text = await self.read_current_page()

                if self.tts:
                    await self.tts.speak(
                        current_text,
                        next_text=next_text,
                    )

                current_text = next_text

            except Exception as e:
                print(f"Reader error: {e}")
                await asyncio.sleep(1)

        if self.tts:
            await self.tts.cleanup()

import asyncio
from typing import Optional, Tuple
from services.tts_service import TTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.kindle_controller import KindleController
import config
import os


class KindleReaderOrchestrator:
    """Coordinates the reading flow"""

    def __init__(
        self,
        tts_service: TTSService,
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
        """Load crop settings from config file"""
        return (config.CROP_LEFT, config.CROP_TOP, config.CROP_RIGHT, config.CROP_BOTTOM)

    async def initialize(self):
        """Initialize all services"""
        await self.tts.initialize()
        if not self.kindle.find_window():
            raise RuntimeError("Kindle window not found")

    async def read_current_page(self) -> Optional[str]:
        """Capture and OCR current page"""
        if not self.kindle.is_valid():
            raise RuntimeError("Kindle window no longer valid")

        screenshot = self.screen_capture.capture_window(
            self.kindle.hwnd,
            crop=self.crop_settings
        )

        if not screenshot:
            print("Screenshot is blank/empty.")
            return None

        text = await self.ocr.extract_text(screenshot)
        if text:
            print("Detected text:\n", text)
        else:
            print("No text detected on this page.")

        return text
    
    async def run_with_callbacks(self, stop_event, on_page_update=None, on_sentence_update=None, on_time_update=None):
        await self.initialize()

        last_text = None
        current_audio = "temp_speech_current.wav"
        next_audio = "temp_speech_next.wav"
        buffer_ratio = 0.3  # turn page 30% before audio ends
        next_text = None
        next_duration = 0

        # Preload first page
        text = await self.read_current_page()
        if text:
            last_text = text
            if on_page_update:
                on_page_update(text)
            next_duration = await self.tts.generate_audio(text, file_path=current_audio)
            if on_time_update:
                on_time_update(next_duration)
        else:
            next_duration = 0

        while not stop_event.is_set():
            try:
                # Start playing current audio
                play_task = asyncio.create_task(self.tts.speak_file(current_audio))

                # While current audio plays, prefetch next page
                await asyncio.sleep(next_duration * (1 - buffer_ratio))
                self.kindle.turn_page()
                print("Page turned!")

                # Small delay to let Kindle render
                await asyncio.sleep(0.2)

                # Capture and OCR the next page
                next_text = await self.read_current_page()
                if next_text and next_text != last_text:
                    last_text = next_text
                    if on_page_update:
                        on_page_update(next_text)
                    # Generate audio in background
                    next_duration = await self.tts.generate_audio(next_text, file_path=next_audio)
                    if on_time_update:
                        on_time_update(next_duration)
                else:
                    next_text = None
                    next_duration = 1  # fallback wait if no new text

                # Wait for current audio to finish before swapping files
                await play_task

                # Swap current/next audio files
                current_audio, next_audio = next_audio, current_audio

            except RuntimeError as e:
                print(f"Error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                await asyncio.sleep(1)

        await self.tts.cleanup()


    async def run(self, stop_event: asyncio.Event):
        """Continuous reading loop with next-page prefetching."""
        await self.initialize()

        last_text = None
        current_audio = "temp_speech_current.wav"
        next_audio = "temp_speech_next.wav"
        buffer_ratio = 0.3  # turn page 30% before audio ends
        next_text = None
        next_duration = 0

        # Preload first page
        text = await self.read_current_page()
        if text:
            last_text = text
            next_duration = await self.tts.generate_audio(text, file_path=current_audio)
        else:
            next_duration = 0

        while not stop_event.is_set():
            try:
                # Start playing current audio
                play_task = asyncio.create_task(self.tts.speak_file(current_audio))

                # While current audio plays, prefetch next page
                await asyncio.sleep(next_duration * (1 - buffer_ratio))
                self.kindle.turn_page()
                print("Page turned!")

                # Small delay to let Kindle render
                await asyncio.sleep(0.2)

                # Capture and OCR the next page
                next_text = await self.read_current_page()
                if next_text and next_text != last_text:
                    last_text = next_text
                    # Generate audio in background
                    next_duration = await self.tts.generate_audio(next_text, file_path=next_audio)
                else:
                    next_text = None
                    next_duration = 1  # fallback wait if no new text

                # Wait for current audio to finish before swapping files
                await play_task

                # Swap current/next audio files
                current_audio, next_audio = next_audio, current_audio

            except RuntimeError as e:
                print(f"Error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                await asyncio.sleep(1)

        await self.tts.cleanup()




#!/usr/bin/env python3
"""
Example: Using AllTalk TTS Service with KindleReaderOrchestrator

This script demonstrates how to use the AllTalk TTS service integrated
with the KindleReader application.

Prerequisites:
- AllTalk TTS server running on http://127.0.0.1:7851
  See: https://github.com/erew123/alltalk_tts
- KindleReader dependencies installed (requirements.txt)
"""

import asyncio
from services.tts_alltalk import AllTalkTTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.WindowController import WindowController
from orchestrator import KindleReaderOrchestrator
import config
from utils import resource_path


async def main():
    """Run KindleReader with AllTalk TTS service."""
    
    # Initialize AllTalk TTS Service
    print("Initializing AllTalk TTS Service...")
    tts = AllTalkTTSService(
        voice="female_06.wav",          # Voice file from AllTalk
        language="en",                  # Language
        volume=100,                     # Volume 1-100
        rate=1.0,                       # Speech rate
        server_url="http://127.0.0.1:7851",  # AllTalk server URL
    )
    
    # Initialize window controller
    print("Finding Kindle window...")
    window_controller = WindowController()
    if not window_controller.find_window("Kindle for PC"):
        print("Warning: Kindle for PC window not found. Looking for any window...")
        windows = window_controller.get_all_windows()
        if windows:
            print(f"Available windows: {windows[:5]}")
        return
    
    # Initialize OCR and screen capture
    screen_capture = ScreenCaptureService()
    ocr = OCRService(tesseract_path=resource_path(config.TESSERACT_PATH))
    
    # Create orchestrator with AllTalk service
    orchestrator = KindleReaderOrchestrator(
        tts_service=tts,
        kindle_controller=window_controller,
        screen_capture=screen_capture,
        ocr_service=ocr,
    )
    
    # Run the reader
    stop_event = asyncio.Event()
    try:
        await orchestrator.run(stop_event)
    except KeyboardInterrupt:
        print("\nStopping...")
        stop_event.set()
    finally:
        await tts.cleanup()


async def test_alltalk_tts():
    """Quick test of AllTalk TTS service."""
    
    print("Testing AllTalk TTS Service...")
    
    tts = AllTalkTTSService(
        voice="female_06.wav",
        language="en",
        volume=100,
    )
    
    # Initialize and test
    await tts.initialize()
    
    test_text = "Hello! This is a test of the AllTalk text to speech service."
    print(f"Generating speech for: {test_text}")
    
    duration, page_turn_delay = await tts.speak(test_text)
    
    print(f"Duration: {duration:.2f}s")
    print(f"Page turn delay: {page_turn_delay:.2f}s")
    
    # Wait for playback to complete
    await tts.wait_for_playback()
    print("Test complete!")
    
    await tts.cleanup()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run quick test
        asyncio.run(test_alltalk_tts())
    else:
        # Run full reader
        asyncio.run(main())

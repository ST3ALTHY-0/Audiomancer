import asyncio

from orchestrator import KindleReaderOrchestrator
from services.tts_python import CoquiTTSService  # or tts_tcp.TCPTTSService
from services.screen_capture import ScreenCaptureService
from services.ocr_service import OCRService
from controllers.WindowController import WindowController
import config
from utils import resource_path

async def main():
    # Initialize services with dependency injection
    # Use Coqui TTS by default
    tts = CoquiTTSService(
        model=getattr(config, 'COQUI_MODEL', 'tts_models/en/vctk/vits'),
        voice=getattr(config, 'COQUI_VOICE', None),
        rate=float(getattr(config, 'TTS_RATE', 1.0)),
        volume=int(getattr(config, 'TTS_VOLUME', 100)),
        espeak_path=getattr(config, 'COQUI_ESPEAK_PATH', None),
    )
    
    window_controller = WindowController()
    # Try to find Kindle for PC by default, or user can modify this to any window title
    if not window_controller.find_window("Kindle for PC"):
        print("Warning: Kindle for PC window not found. Looking for any window...")
        windows = window_controller.get_all_windows()
        if windows:
            print(f"Available windows: {windows[:5]}")  # Show first 5 windows
            print("Please modify main.py to specify the correct window title")
        return
    
    screen_capture = ScreenCaptureService()
    ocr = OCRService(tesseract_path=resource_path(config.TESSERACT_PATH))
    
    orchestrator = KindleReaderOrchestrator(
        tts_service=tts,
        kindle_controller=window_controller,
        screen_capture=screen_capture,
        ocr_service=ocr,
        # crop_settings defaults to utils.get_crop_settings()
    )
    
    stop_event = asyncio.Event()
    
    try:
        await orchestrator.run(stop_event)
    except KeyboardInterrupt:
        print("\nStopping...")
        stop_event.set()

if __name__ == "__main__":
    asyncio.run(main())
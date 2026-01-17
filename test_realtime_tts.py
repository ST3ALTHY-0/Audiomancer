"""
Test script for RealTimeTTS integration
"""
import asyncio
from src.services.tts_realtime import RealTimeTTSService


async def test_realtime_tts():
    print("Testing RealTimeTTS with VCTK/VITS...")
    
    # Create service
    tts = RealTimeTTSService(
        model_name="tts_models/en/vctk/vits",
        speaker="p225",
        rate=1.0,
        volume=100,
        device="cuda"  # Use GPU if available
    )
    
    # Initialize
    print("Initializing...")
    await tts.initialize()
    
    # Test speech
    print("Speaking test text...")
    test_text = "Hello! This is a test of real-time text to speech streaming using the VCTK VITS model."
    await tts.speak(test_text)
    
    # Wait for playback to complete
    print("Waiting for playback to complete...")
    await asyncio.sleep(5)
    
    # Cleanup
    print("Cleaning up...")
    await tts.cleanup()
    
    print("Test complete!")


if __name__ == "__main__":
    asyncio.run(test_realtime_tts())

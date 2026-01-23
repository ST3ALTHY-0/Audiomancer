"""
Stream TTS audio and play it in real-time
"""

import requests
import sounddevice as sd
import soundfile as sf
import io
import sys


def stream_and_play(text, voice="female_01.wav", language="en", api_base="http://127.0.0.1:7851"):
    """
    Stream TTS audio and play it immediately.
    
    Args:
        text: Text to generate
        voice: Voice file to use
        language: Language code
        api_base: AllTalk API base URL
    """
    url = f"{api_base}/api/tts-generate-streaming"
    
    data = {
        "text": text,
        "voice": voice,
        "language": language,
        "output_file": "stream_output.wav"
    }
    
    print(f"Streaming TTS for: {text[:100]}...")
    
    try:
        # Stream the response
        response = requests.post(url, data=data, stream=True)
        response.raise_for_status()
        
        # Read all streaming data into memory
        audio_data = io.BytesIO()
        json_data = b''
        chunk_count = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                audio_data.write(chunk)
                chunk_count += 1
        
        # Reset to beginning
        audio_data.seek(0)
        
        print(f"Received {chunk_count} chunks, {audio_data.getbuffer().nbytes} total bytes")
        
        # The response might contain JSON metadata at the end
        # Try to load and play the audio
        try:
            print("Loading audio...")
            audio_array, samplerate = sf.read(audio_data)
            print(f"Audio loaded: {len(audio_array)} samples @ {samplerate}Hz")
            
            print("Playing audio...")
            sd.play(audio_array, samplerate)
            sd.wait()  # Wait until audio finishes
            print("✓ Playback complete")
        except Exception as e:
            print(f"Audio playback failed: {e}")
            print(f"Response content type: {response.headers.get('content-type')}")
            print(f"First 500 bytes: {audio_data.getvalue()[:500]}")
            raise
        
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Example usage
    text = """Ahead of him was the Temple of Ashes, a stepped pyramid several hundred 
    feet high looming above the bay. It was by edict the tallest building in the city."""
    
    stream_and_play(
        text=text,
        voice="female_01.wav",
        language="en"
    )

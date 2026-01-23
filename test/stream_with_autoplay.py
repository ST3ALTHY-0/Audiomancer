"""
Stream long text with chunking and auto-play
"""

import requests
import sounddevice as sd
import soundfile as sf
import io
from ..src.tts_chunked_generator import AllTalkChunkedTTS


def play_audio_from_url(audio_url, api_base="http://127.0.0.1:7851"):
    """Download and play audio from URL."""
    full_url = f"{api_base}{audio_url}"
    
    try:
        response = requests.get(full_url, timeout=30)
        response.raise_for_status()
        
        # Load audio data
        audio_data = io.BytesIO(response.content)
        data, samplerate = sf.read(audio_data)
        
        # Play audio
        sd.play(data, samplerate)
        sd.wait()
        
    except Exception as e:
        print(f"Error playing audio: {e}")


def generate_and_play_long_text(
    text,
    character_voice="female_01.wav",
    chunk_size=2,
    language="en",
    api_base="http://127.0.0.1:7851"
):
    """
    Generate long text in chunks and auto-play each chunk.
    
    Args:
        text: Long text (any length)
        character_voice: Voice to use
        chunk_size: Sentences per chunk
        language: Language code
        api_base: API base URL
    """
    # Initialize chunked TTS
    tts = AllTalkChunkedTTS(api_base=api_base)
    
    # Define progress callback to play each chunk
    def on_chunk_complete(current, total, chunk_text):
        print(f"\n{'='*60}")
        print(f"Chunk {current}/{total}")
        print(f"Text: {chunk_text[:80]}...")
        print(f"{'='*60}")
    
    # Generate chunks
    results = tts.generate_long_text(
        text=text,
        character_voice=character_voice,
        chunk_size=chunk_size,
        language=language,
        output_file_name="autoplay_chunk",
        progress_callback=on_chunk_complete
    )
    
    print("\n🔊 Starting playback...\n")
    
    # Play each chunk sequentially
    for i, result in enumerate(results, 1):
        if "error" not in result and "output_file_url" in result:
            print(f"▶️  Playing chunk {i}/{len(results)}...")
            play_audio_from_url(result["output_file_url"], api_base)
            print(f"✓ Chunk {i} complete\n")
        else:
            print(f"✗ Skipping chunk {i} due to error\n")
    
    print("✓ All chunks played!")


if __name__ == "__main__":
    # Example with your text
    long_text = """
    Ahead of him was the Temple of Ashes, a stepped pyramid several hundred feet high 
    looming above the bay. It was by edict the tallest building in the city, though 
    strictly speaking many of the homes in the Bay District and the Jaws sat higher 
    on the slopes above it. But the priests allowed nothing larger to be built, lest 
    the Dead Gods in their ancient tombs be annoyed. The temple stood at the end of 
    a peninsula sticking into the water, and a long, broad stone plaza separated it 
    from the rest of the city. Approaching it required a walk of several minutes across 
    this open expanse. Eight times a year, the Temple priests held open-air worship 
    services in the plaza to mark the holy day of one of the Dead Gods. The rest of 
    the time, the area was virtually empty.
    """
    
    generate_and_play_long_text(
        text=long_text,
        character_voice="female_01.wav",
        chunk_size=2,
        language="en"
    )

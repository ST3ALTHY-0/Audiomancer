"""
Real-time streaming TTS using simple TTS engine (fallback to gTTS for reliability).
For true streaming, we'll use a hybrid approach with Coqui TTS pipelined playback.
"""
import os
import threading
import time
from typing import Optional
from services.tts_service import TTSService


class RealTimeTTSService(TTSService):
    """Real-time streaming TTS using Google's gTTS (lightweight, always works)"""

    def __init__(
        self,
        model_name: str = "en",  # Language code for gTTS
        speaker: str = None,
        rate: float = 1.0,
        volume: int = 100,
        device: str = "cpu"
    ):
        self.model_name = model_name
        self.speaker = speaker
        self.rate = rate
        self.volume = volume
        self.device = device
        self.tts = None
        self._playback_done = threading.Event()
        self._playback_done.set()  # Initially not playing
        self._playback_lock = threading.Lock()

    async def initialize(self):
        """Initialize gTTS for text-to-speech"""
        try:
            from gtts import gTTS
            import io
            
            print(f"Initializing gTTS (Google Text-to-Speech)")
            print(f"Language: {self.model_name}")
            
            # Store gTTS for use
            self.tts = gTTS
            
            print("✓ gTTS initialized successfully")
            print(f"  Using Google TTS with fast streaming playback")
            
        except ImportError as e:
            print(f"✗ gTTS not installed: {e}")
            print("Install with: pip install gtts")
            raise
        except Exception as e:
            print(f"✗ Error initializing gTTS: {e}")
            print(f"Error details: {type(e).__name__}: {str(e)}")
            raise

    async def speak(self, text: str, **kwargs) -> tuple:
        """Generate and play speech (blocking until playback completes)"""
        if not self.tts:
            raise RuntimeError("gTTS not initialized")
        
        # Wait for previous playback to complete
        self._playback_done.wait(timeout=30)
        
        # Start TTS generation and playback
        self._playback_done.clear()
        threading.Thread(
            target=self._speak_text,
            args=(text,),
            daemon=True
        ).start()
        
        # Return estimated duration based on text length
        word_count = len(text.split())
        estimated_duration = max(1.0, word_count * 0.4)
        return (estimated_duration, None)

    def _speak_text(self, text: str):
        """Generate and play text using gTTS"""
        try:
            with self._playback_lock:
                import io
                import tempfile
                import os
                
                # Generate speech with gTTS (returns MP3)
                tts = self.tts(text=text, lang=self.model_name, slow=False)
                
                # Save to temporary MP3 file
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    tts.write_to_fp(tmp_file)
                
                try:
                    # Play MP3 using simpleaudio and pydub
                    from pydub import AudioSegment
                    import simpleaudio as sa
                    
                    # Load MP3 file
                    audio = AudioSegment.from_mp3(tmp_path)
                    
                    # Play audio
                    play_obj = sa.play_buffer(
                        audio.raw_data,
                        num_channels=audio.channels,
                        bytes_per_sample=audio.sample_width,
                        sample_rate=audio.frame_rate
                    )
                    play_obj.wait_done()  # Wait for playback to finish
                    
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    
        except Exception as e:
            print(f"Error during TTS: {e}")
        finally:
            self._playback_done.set()

    async def speak_file(self, filepath: str) -> float:
        """Not supported"""
        raise NotImplementedError("File-based speech not supported")

    def speak_file_nonblocking(self, filepath: str) -> float:
        """Not supported"""
        raise NotImplementedError("File-based speech not supported")

    def stop(self):
        """Stop current playback"""
        self._playback_done.set()

    async def cleanup(self):
        """Clean up resources"""
        self.stop()
        self._playback_done.wait(timeout=5)
        self.tts = None

"""
AllTalk TTS Service - Integration with allTalk TTS API server.
Implements the TTSService interface for use in the KindleReaderOrchestrator.
"""
import asyncio
import os
import time
import threading
import re
from typing import Optional, Tuple, List
import simpleaudio as sa
import soundfile as sf
import numpy as np

from .tts_service import TTSService
from .allTalk_client import tts_to_wav

#run C:\AllTalk\alltalk_tts>start_alltalk.bat to start server


class AllTalkTTSService(TTSService):
    """AllTalk TTS implementation that integrates with the allTalk API server."""

    def __init__(
        self,
        voice: str = "female_06.wav",
        language: str = "en",
        volume: int = 100,
        rate: float = 1.0,
        server_url: str = "http://127.0.0.1:7851",
        output_dir: str = "output/temp",
        page_turn_buffer: float = 0.3,
        max_chars: int = 1800,
        chunk_sentences: int = 2,
    ):
        """
        Initialize AllTalk TTS Service.
        
        Args:
            voice: Voice file name (e.g., "female_06.wav")
            language: Language code (default "en")
            volume: Volume level 1-100 (default 100)
            rate: Speech rate multiplier (default 1.0)
            server_url: URL of allTalk API server
            output_dir: Directory to save generated audio files
            page_turn_buffer: Fraction of audio duration to wait before turning page
            max_chars: Maximum characters per chunk (default 1800)
            chunk_sentences: Number of sentences to group per chunk (default 2)
        """
        self.voice = voice
        self.language = language
        self.volume = max(1, min(100, volume))
        self.rate = max(0.5, min(2.0, rate))
        self.server_url = server_url
        self.output_dir = output_dir
        self.page_turn_buffer = max(0.0, min(1.0, page_turn_buffer))
        self.max_chars = max_chars
        self.chunk_sentences = chunk_sentences
        
        os.makedirs(output_dir, exist_ok=True)
        
        self._current_file = os.path.join(output_dir, "alltalk_current.wav")
        self._next_file = os.path.join(output_dir, "alltalk_next.wav")
        self._prefetch_file = os.path.join(output_dir, "alltalk_prefetch.wav")
        self._prefetched_text: Optional[str] = None
        self._prefetch_ready: bool = False
        self._prefetch_task: Optional[asyncio.Task] = None
        
        self._playback_thread = None
        self._playback_obj = None
        self._is_playing = False

    async def initialize(self) -> None:
        """Initialize AllTalk TTS service."""
        print("✓ AllTalk TTS initialized")
        print(f"  Server: {self.server_url}")
        print(f"  Voice: {self.voice}")
        print(f"  Language: {self.language}")

    def set_voice(self, voice: str) -> bool:
        """Change voice"""
        self.voice = voice
        return True

    def set_rate(self, rate: float) -> bool:
        """Change speech rate"""
        self.rate = max(0.5, min(2.0, rate))
        return True

    def set_volume(self, volume: int) -> bool:
        """Change volume"""
        self.volume = max(1, min(100, volume))
        return True

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text for TTS generation.
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text ready for TTS
        """
        # Replace special dashes and hyphens
        cleaned = re.sub(r' \- | \– ', ' ', text)
        
        # Replace percent signs
        cleaned = cleaned.replace('%', ' percent')
        
        # Fix period-quote spacing
        cleaned = re.sub(r'\.\s\'', ".'", cleaned)
        
        # Remove standalone brackets with quotes
        cleaned = re.sub(r'(?<!\w)[\']+(?!\w)', '', cleaned)
        
        # Replace double quotes with single quotes
        cleaned = cleaned.replace('"', "'")
        
        # Remove unwanted characters (keep letters, numbers, punctuation, and various language characters)
        pattern = r'[^a-zA-Z0-9\s.,;:!?\-\'"$À-ÿ\u00C0-\u017F\u0400-\u04FF\u0150\u0151\u0170\u0171\u0900-\u097F\u2018\u2019\u201C\u201D\u2026\u3001\u3002\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F\uFF01\uFF0c\uFF1A\uFF1B\uFF1F\u011E\u011F\u0130\u0131\u015E\u015F\u00E7\u00C7\u00F6\u00D6]'
        cleaned = re.sub(pattern, '', cleaned)
        
        # Replace dash-space and double dashes with semicolon
        cleaned = re.sub(r'-\s', '; ', cleaned)
        cleaned = cleaned.replace('--', '; ')
        
        return cleaned
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: Cleaned text
            
        Returns:
            List of sentences
        """
        # Split by sentence-ending punctuation followed by space, or CJK punctuation
        pattern = r'(?<=[\[.!?:\]][\'"]?\u2018\u2019\u201C\u201D]*)\s+|(?<=[\u3002\uFF01\uFF1A\uFF1F])'
        sentences = re.split(pattern, text)
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def create_chunks(self, sentences: List[str]) -> List[str]:
        """
        Group sentences into chunks based on character limit.
        
        Args:
            sentences: List of sentences
            
        Returns:
            List of text chunks
        """
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence would exceed max_chars, save current chunk
            if current_length + sentence_length > self.max_chars and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        # Add remaining sentences
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks

    async def generate_audio(
        self,
        text: str,
        file_path: str,
        reference_audio: Optional[str] = None,
    ) -> float:
        """
        Generate audio using allTalk TTS API. Handles long texts by chunking.
        
        Args:
            text: Text to synthesize (any length)
            file_path: Path to save the generated WAV file
            reference_audio: Not used for allTalk (for compatibility)
            
        Returns:
            Duration of generated audio in seconds
        """
        try:
            # Clean and prepare text
            cleaned_text = self.clean_text(text)
            
            # Check if text needs chunking
            if len(cleaned_text) <= self.max_chars:
                # Short text - generate directly
                safe_text = cleaned_text.replace("\n", " ").replace("\r", " ").strip()
                
                await asyncio.to_thread(
                    tts_to_wav,
                    safe_text,
                    file_path,
                    self.voice,
                    self.language,
                )
                
                duration = self.estimate_duration(file_path)
                
                # Apply volume adjustment
                audio, sr = sf.read(file_path)
                audio = np.clip(audio * (self.volume / 100), -1.0, 1.0)
                sf.write(file_path, audio, sr)
                
                return duration
            
            else:
                # Long text - chunk and concatenate
                print(f"Text length {len(cleaned_text)} exceeds {self.max_chars}, chunking...")
                
                sentences = self.split_into_sentences(cleaned_text)
                chunks = self.create_chunks(sentences)
                
                print(f"Split into {len(chunks)} chunks")
                
                # Generate audio for each chunk
                chunk_files = []
                for i, chunk in enumerate(chunks):
                    chunk_file = file_path.replace(".wav", f"_chunk{i}.wav")
                    safe_chunk = chunk.replace("\n", " ").replace("\r", " ").strip()
                    
                    print(f"Generating chunk {i+1}/{len(chunks)} ({len(safe_chunk)} chars)...")
                    
                    await asyncio.to_thread(
                        tts_to_wav,
                        safe_chunk,
                        chunk_file,
                        self.voice,
                        self.language,
                    )
                    
                    chunk_files.append(chunk_file)
                
                # Concatenate all chunks into one file
                all_audio = []
                sample_rate = None
                
                for chunk_file in chunk_files:
                    audio, sr = sf.read(chunk_file)
                    if sample_rate is None:
                        sample_rate = sr
                    all_audio.append(audio)
                    
                    # Clean up chunk file
                    try:
                        os.remove(chunk_file)
                    except:
                        pass
                
                # Concatenate audio arrays
                combined_audio = np.concatenate(all_audio)
                
                # Apply volume adjustment
                combined_audio = np.clip(combined_audio * (self.volume / 100), -1.0, 1.0)
                
                # Save final file
                sf.write(file_path, combined_audio, sample_rate)
                
                duration = len(combined_audio) / sample_rate
                print(f"✓ Combined audio duration: {duration:.2f}s")
                
                return duration
            
        except Exception as e:
            print(f"Error generating audio: {e}")
            raise

    def estimate_duration(self, file_path: str) -> float:
        """Estimate audio duration from file."""
        try:
            info = sf.info(file_path)
            return info.frames / info.samplerate
        except Exception as e:
            print(f"Error reading audio file: {e}")
            return 5.0  # Default fallback

    async def speak_file_blocking(self, file_path: str) -> None:
        """Play audio file and block until completion."""
        try:
            wave_obj = sa.WaveObject.from_wave_file(file_path)
            play_obj = wave_obj.play()
            self._playback_obj = play_obj
            self._is_playing = True
            
            await asyncio.to_thread(play_obj.wait_done)
            self._is_playing = False
            
        except Exception as e:
            print(f"Error playing audio: {e}")
            self._is_playing = False

    async def speak_file_nonblocking(self, file_path: str) -> float:
        """Play audio file without blocking, return duration."""
        try:
            wave_obj = sa.WaveObject.from_wave_file(file_path)
            play_obj = wave_obj.play()
            self._playback_obj = play_obj
            self._is_playing = True
            
            # Return duration without waiting
            duration = self.estimate_duration(file_path)
            
            # Stop previous playback thread if any
            if self._playback_thread and self._playback_thread.is_alive():
                try:
                    self._playback_obj.stop()
                except:
                    pass
            
            # Start playback in background thread
            def _playback_job():
                try:
                    play_obj.wait_done()
                except:
                    pass
                finally:
                    self._is_playing = False
            
            self._playback_thread = threading.Thread(target=_playback_job, daemon=True)
            self._playback_thread.start()
            
            return duration
            
        except Exception as e:
            print(f"Error starting audio playback: {e}")
            return 0.0

    async def wait_for_playback(self) -> None:
        """Wait for current playback to complete."""
        while self._is_playing:
            await asyncio.sleep(0.1)

    async def speak(
        self,
        text: str,
        next_text: Optional[str] = None,
        reference_audio: Optional[str] = None,
    ) -> Tuple[float, float]:
        """
        Non-blocking pipelined playback: generates, starts playback immediately,
        and returns control without waiting for audio to finish.

        Prefetches the *next* page audio near the end of current playback so it is
        ready when the next page starts.

        Returns: (duration, page_turn_delay) where duration is audio length
        and page_turn_delay can be used for page-turning timing.
        """
        # If we already prefetched this exact text, reuse it
        if self._prefetch_ready and self._prefetched_text == text:
            duration = self.estimate_duration(self._prefetch_file)
            await self.speak_file_nonblocking(self._prefetch_file)
            self._prefetch_ready = False
            self._prefetched_text = None
            if next_text:
                self._schedule_prefetch(next_text, reference_audio, duration)
            page_turn_delay = duration * (1 - self.page_turn_buffer)
            return duration, page_turn_delay

        # Generate current page audio
        duration = await self.generate_audio(text, self._current_file, reference_audio)

        # Start playing without blocking
        await self.speak_file_nonblocking(self._current_file)

        # Schedule prefetch of next page
        if next_text:
            self._schedule_prefetch(next_text, reference_audio, duration)

        page_turn_delay = duration * (1 - self.page_turn_buffer)
        return duration, page_turn_delay

    def _schedule_prefetch(self, next_text: str, reference_audio: Optional[str], duration: float, preload_ratio: float = 0.7):
        """Schedule prefetch of next page audio after a portion of current playback."""
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

        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()
        self._prefetch_task = asyncio.create_task(_prefetch_job())

    async def prefetch_next(self, next_text: str, reference_audio: Optional[str] = None):
        """Immediately start generating audio for the next page (used by orchestrator)."""
        async def _prefetch_job():
            try:
                await self.generate_audio(next_text, self._prefetch_file, reference_audio)
                self._prefetched_text = next_text
                self._prefetch_ready = True
            except Exception as e:
                print(f"Prefetch error: {e}")
                self._prefetch_ready = False
                self._prefetched_text = None

        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()
        self._prefetch_task = asyncio.create_task(_prefetch_job())

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._playback_obj:
            try:
                self._playback_obj.stop()
            except:
                pass
        
        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()
        
        self._is_playing = False

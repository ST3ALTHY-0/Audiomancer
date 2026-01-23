from abc import ABC, abstractmethod
from typing import Optional, Tuple

class TTSService(ABC):
    """Abstract base class for TTS implementations"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the TTS service"""
        pass
    
    @abstractmethod
    async def speak(
        self,
        text: str,
        next_text: Optional[str] = None,
        reference_audio: Optional[str] = None,
    ) -> Tuple[float, float]:
        """Speak the given text
        
        Returns: (duration, page_turn_delay) tuple
            - duration: total audio duration in seconds
            - page_turn_delay: recommended delay before turning page
        """
        pass
    
    @abstractmethod
    async def prefetch_next(
        self,
        next_text: str,
        reference_audio: Optional[str] = None,
    ) -> None:
        """Prefetch audio for next text to enable smooth playback"""
        pass
    
    @abstractmethod
    async def wait_for_playback(self) -> None:
        """Wait for current playback to complete"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass
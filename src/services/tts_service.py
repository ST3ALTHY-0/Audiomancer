from abc import ABC, abstractmethod
from typing import Optional

class TTSService(ABC):
    """Abstract base class for TTS implementations"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the TTS service"""
        pass
    
    # @abstractmethod
    # async def speak(self, text: str) -> None:
    #     """Speak the given text"""
    #     pass
    
    # @abstractmethod
    # async def set_voice(self, voice: str) -> bool:
    #     """Change voice, return success"""
    #     pass
    
    # @abstractmethod
    # async def set_rate(self, rate: float) -> bool:
    #     """Change speech rate"""
    #     pass
    
    # @abstractmethod
    # async def set_volume(self, volume: int) -> bool:
    #     """Change volume"""
    #     pass
    
    # @abstractmethod
    # def estimate_duration(self, text: str) -> float:
    #     """Estimate how long speech will take"""
    #     pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass
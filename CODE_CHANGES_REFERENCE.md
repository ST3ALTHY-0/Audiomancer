# Code Changes Reference

## File 1: src/services/tts_service.py

### Change: Complete the abstract interface

```python
# BEFORE (commented out methods)
from abc import ABC, abstractmethod
from typing import Optional

class TTSService(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass
    
    # All other methods were commented out
    
    @abstractmethod
    async def cleanup(self) -> None:
        pass

# AFTER (complete interface)
from abc import ABC, abstractmethod
from typing import Optional, Tuple

class TTSService(ABC):
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
        """
        pass
    
    @abstractmethod
    async def prefetch_next(
        self,
        next_text: str,
        reference_audio: Optional[str] = None,
    ) -> None:
        """Prefetch audio for next text"""
        pass
    
    @abstractmethod
    async def wait_for_playback(self) -> None:
        """Wait for current playback to complete"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass
```

---

## File 2: src/orchestrator.py

### Change 1: Remove page_delay_seconds parameter

```python
# BEFORE
def __init__(
    self,
    tts_service: Optional[TTSService],
    kindle_controller: WindowController,
    screen_capture: ScreenCaptureService,
    ocr_service: OCRService,
    crop_settings: Optional[Tuple[int, int, int, int]] = None,
    page_delay_seconds: Optional[float] = None,  # REMOVED
):
    self.tts = tts_service
    self.kindle = kindle_controller
    self.screen_capture = screen_capture
    self.ocr = ocr_service
    self.crop_settings = crop_settings or self._load_crop_settings_from_config()
    # REMOVED: page_turn_timing calculation
    try:
        self.page_turn_timing = max(0.0, min(1.0, float(page_delay_seconds))) if page_delay_seconds is not None else 0.72
    except Exception:
        self.page_turn_timing = 0.72

# AFTER
def __init__(
    self,
    tts_service: Optional[TTSService],
    kindle_controller: WindowController,
    screen_capture: ScreenCaptureService,
    ocr_service: OCRService,
    crop_settings: Optional[Tuple[int, int, int, int]] = None,
):
    self.tts = tts_service
    self.kindle = kindle_controller
    self.screen_capture = screen_capture
    self.ocr = ocr_service
    self.crop_settings = crop_settings or self._load_crop_settings_from_config()
```

### Change 2: Update _play_tts_service return type and usage

```python
# BEFORE
async def _play_tts_service(
    self,
    current_text: str,
    next_text: Optional[str],
    reference_audio: Optional[str],
    on_time_update
) -> Tuple[float, Optional[asyncio.Task]]:
    """Play text using TTS service and return duration and playback task."""
    duration, _ = await self.tts.speak(  # Discarded page_turn_delay!
        current_text,
        next_text=next_text,
        reference_audio=reference_audio,
    )
    playback_task = asyncio.create_task(self.tts.wait_for_playback())
    
    print(f"[DEBUG] Duration: {duration:.2f}s, {len(current_text)} chars, {len(current_text.split())} words")
    
    if on_time_update:
        on_time_update(duration)
    
    return duration, playback_task

# AFTER
async def _play_tts_service(
    self,
    current_text: str,
    next_text: Optional[str],
    reference_audio: Optional[str],
    on_time_update
) -> Tuple[float, float, Optional[asyncio.Task]]:
    """Play text using TTS service and return duration, page_turn_delay, and playback task.
    
    Returns:
        Tuple of (duration, page_turn_delay, playback_task)
    """
    duration, page_turn_delay = await self.tts.speak(  # Now use the delay!
        current_text,
        next_text=next_text,
        reference_audio=reference_audio,
    )
    playback_task = asyncio.create_task(self.tts.wait_for_playback())
    
    print(
        f"[DEBUG] Duration: {duration:.2f}s, Page Turn Delay: {page_turn_delay:.2f}s, "
        f"{len(current_text)} chars, {len(current_text.split())} words")
    
    if on_time_update:
        on_time_update(duration)
    
    return duration, page_turn_delay, playback_task
```

### Change 3: Restructure run_with_callbacks for proper prefetching and timing

```python
# BEFORE
async def run_with_callbacks(self, ...):
    await self.initialize()
    current_text = await self.read_current_page()
    # ... UI setup ...
    
    while not stop_event.is_set():
        try:
            # PROBLEM: Play before reading next page
            if xtts_streaming:
                await self._play_xtts_streaming(current_text)
                duration = 0.5
            elif self.tts:
                duration, playback_task = await self._play_tts_service(...)  # Lost page_turn_delay
            
            # PROBLEM: Use self.page_turn_timing instead of service-provided delay
            turn_delay = max(0.1, duration * self.page_turn_timing) if duration else 0.3
            await asyncio.sleep(turn_delay)
            
            self.kindle.turn_page()
            await asyncio.sleep(0.2)
            
            # PROBLEM: Read page AFTER turning (late for prefetch)
            next_text = await self.read_current_page()
            if next_text == last_text:
                next_text = None
            
            if on_page_update and next_text:
                on_page_update(next_text)
            
            # PROBLEM: Redundant prefetch call (already handled in speak())
            if self.tts and next_text:
                await self.tts.prefetch_next(next_text, reference_audio)
                print("[DEBUG] Prefetch started for next page")
            
            # Wait for playback
            if playback_task:
                try:
                    await playback_task
                except Exception as e:
                    print(f"Playback wait error: {e}")
            
            last_text = current_text
            current_text = next_text
            # ...

# AFTER
async def run_with_callbacks(self, ...):
    await self.initialize()
    current_text = await self.read_current_page()
    # ... UI setup ...
    
    while not stop_event.is_set():
        try:
            # IMPROVEMENT: Read next page FIRST (enables early prefetch)
            next_text = await self.read_current_page()
            if next_text == last_text:
                next_text = None
            
            # Update UI with new page
            if on_page_update and next_text:
                on_page_update(next_text)
            
            # IMPROVEMENT: Get timing from TTS service
            if xtts_streaming:
                await self._play_xtts_streaming(current_text)
                duration = 0.5
                page_turn_delay = duration * 0.7  # Default 70%
            elif self.tts:
                # Service.speak() now passes next_text for internal prefetch
                # Returns: (duration, page_turn_delay, playback_task)
                duration, page_turn_delay, playback_task = await self._play_tts_service(
                    current_text, next_text, reference_audio, on_time_update
                )
            
            # IMPROVEMENT: Use service-provided timing
            print(f"[DEBUG] Waiting {page_turn_delay:.2f}s before turning page")
            await asyncio.sleep(page_turn_delay)
            
            self.kindle.turn_page()
            await asyncio.sleep(0.2)
            
            # REMOVED: Redundant prefetch call (handled in speak())
            # Prefetch is now scheduled internally by TTS service
            
            # Wait for playback
            if playback_task:
                try:
                    await playback_task
                except Exception as e:
                    print(f"Playback wait error: {e}")
            
            last_text = current_text
            current_text = next_text
            # ...
```

---

## Summary of Code Changes

| Component | Change Type | Lines | Impact |
|-----------|------------|-------|--------|
| tts_service.py | Added methods | ~30 | Full interface definition |
| orchestrator.py | Removed parameter | -12 | Simplified API |
| orchestrator.py | Updated method | +5 lines | Better return info |
| orchestrator.py | Restructured loop | -25 lines | Cleaner flow |
| orchestrator.py | Removed code | -5 lines | Eliminated redundancy |

## Result

- ✓ Unified timing source (service-provided delays)
- ✓ Eliminated redundant prefetch calls
- ✓ Improved page reading order (earlier prefetch opportunity)
- ✓ Better code clarity and maintainability
- ✓ Enhanced debug logging
- ✓ Single responsibility principle maintained

# TTS AllTalk Integration Improvements

## Summary of Changes

The integration between `tts_alltalk.py` and `orchestrator.py` has been improved to ensure proper delay handling and prefetching.

## Key Improvements

### 1. **Complete TTSService Interface** (`tts_service.py`)
- Added abstract method definitions for `speak()`, `prefetch_next()`, and `wait_for_playback()`
- Clarified return type: `Tuple[float, float]` where:
  - `duration`: total audio duration in seconds
  - `page_turn_delay`: TTS-recommended delay before turning page

### 2. **Unified Delay Handling** (`orchestrator.py`)
- **Removed redundant `page_turn_timing` parameter** that was passed to the constructor
- Now uses **TTS service-provided delay timing** which is more intelligent and service-aware
- The AllTalkTTSService calculates optimal page-turn timing based on `page_turn_buffer` (default 0.3 = turn at 70% of playback)

**Before:**
```python
# Two conflicting sources of timing:
turn_delay = max(0.1, duration * self.page_turn_timing)  # Orchestrator's fixed timing
# vs. also ignoring what TTS service returned
duration, _ = await self.tts.speak(...)  # Discarded the page_turn_delay!
```

**After:**
```python
# Single source of truth - from TTS service
duration, page_turn_delay = await self.tts.speak(...)
await asyncio.sleep(page_turn_delay)  # Use service-provided timing
```

### 3. **Proper Prefetch Integration** (`orchestrator.py`)
- **Removed redundant manual prefetch calls**
- AllTalkTTSService already schedules prefetching internally when `speak()` is called with `next_text`
- The service intelligently prefetches at 70% of current audio playback (configurable via `page_turn_buffer`)

**Before:**
```python
# Conflicting prefetch approaches:
duration, playback_task = await self._play_tts_service(...)
# ... manually call prefetch again (redundant!)
if self.tts and next_text:
    await self.tts.prefetch_next(next_text, reference_audio)
```

**After:**
```python
# Single prefetch mechanism - embedded in speak()
duration, page_turn_delay, playback_task = await self._play_tts_service(
    current_text, next_text, reference_audio, on_time_update
)
# AllTalkTTSService handles prefetch internally with _schedule_prefetch()
```

### 4. **Improved Page Reading Order** (`orchestrator.py`)
- Read next page **before** playing current audio (not after)
- This allows TTS service to begin prefetching immediately while current audio starts
- Reduces delays between pages for smoother reading experience

**Before:**
```
1. Play audio for page 1
2. Wait for page turn delay
3. Turn page
4. Read page 2
5. Start prefetch for page 2 (late!)
```

**After:**
```
1. Read page 2
2. Play audio for page 1 (with page 2 passed to prefetch)
3. Prefetch for page 2 starts immediately (~70% through page 1 audio)
4. Wait for page turn delay
5. Turn page
```

### 5. **Enhanced Debug Logging**
Added explicit logging of page turn delay:
```python
print(f"[DEBUG] Waiting {page_turn_delay:.2f}s before turning page")
```

## AllTalkTTSService Features

The AllTalkTTSService includes built-in optimizations:

### Internal Prefetching (`_schedule_prefetch`)
- Automatically prefetches the next page at 70% of current playback (configurable)
- Runs in background async task
- Prevents cache misses when transitioning between pages

### Delay Calculation
```python
page_turn_delay = duration * (1 - self.page_turn_buffer)
# With default buffer of 0.3:
# page_turn_delay = duration * 0.7 (turn at 70% of playback)
```

### Playback Handling
- Non-blocking playback with threading
- `wait_for_playback()` allows orchestrator to wait when needed
- Proper cleanup of playback threads on exit

## Configuration

### Adjusting Page Turn Timing

Modify in `main.py`:
```python
tts = AllTalkTTSService(
    voice="female_06.wav",
    page_turn_buffer=0.3,  # 0.3 = turn at 70%, 0.5 = turn at 50%, etc.
    # ... other params
)
```

### Prefetch Timing

The prefetch timing (70% of duration) is hardcoded in `_schedule_prefetch()`:
```python
await asyncio.sleep(max(0.0, duration * preload_ratio))  # preload_ratio = 0.7
```

## Testing Recommendations

1. **Page Turn Timing**: Verify the page turns don't overlap with audio playback
2. **Prefetch Success**: Check logs for "Prefetch error" messages
3. **Audio Duration**: Verify `[DEBUG] Duration` matches actual audio length
4. **Smooth Transitions**: Listen for smooth page transitions without gaps or overlaps

## Backward Compatibility

The updated interface is compatible with all existing TTS service implementations:
- `CoquiTTSService` (tts_python.py)
- `AllTalkTTSService` (tts_alltalk.py)
- Any future implementations must follow the TTSService interface

All implementations return `(duration, page_turn_delay)` tuple from `speak()` method.

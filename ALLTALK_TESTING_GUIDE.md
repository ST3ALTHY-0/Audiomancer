# AllTalk TTS Integration Testing Guide

## Quick Start Verification

### 1. Ensure AllTalk Server is Running
```bash
# AllTalk should be running on port 7851
# Check connectivity:
curl http://127.0.0.1:7851/api/models
```

### 2. Configure main.py to Use AllTalk
Uncomment the AllTalkTTSService section in `src/main.py`:

```python
# Option 2: Use AllTalk TTS (requires allTalk server running on port 7851)
tts = AllTalkTTSService(
    voice=getattr(config, 'ALLTALK_VOICE', 'female_06.wav'),
    language=getattr(config, 'ALLTALK_LANGUAGE', 'en'),
    volume=int(getattr(config, 'TTS_VOLUME', 100)),
    rate=float(getattr(config, 'TTS_RATE', 1.0)),
    server_url=getattr(config, 'ALLTALK_SERVER', 'http://127.0.0.1:7851'),
)
```

### 3. Run the Application
```bash
cd src
python main.py
```

## Expected Behavior

### Console Output
You should see debug messages like:
```
✓ AllTalk TTS initialized successfully
  Server: http://127.0.0.1:7851
  Voice: female_06.wav
  Language: en

[DEBUG] Duration: 12.45s, Page Turn Delay: 8.72s, 245 chars, 45 words
[DEBUG] Waiting 8.72s before turning page
```

### Page Turning Behavior
1. **Smooth transitions**: Page should turn ~70% through audio playback (at 8.72s of a 12.45s sample)
2. **No gaps**: Audio should continue playing as page turns
3. **No overlaps**: Audio should finish before moving to next page

### Prefetching
- While page 1 audio plays (at ~70% mark), page 2 audio generation begins silently
- Page 2 should be ready immediately when page 1 finishes
- Check `output/temp/` folder for these files:
  - `alltalk_current.wav` - currently playing audio
  - `alltalk_prefetch.wav` - next page being prefetched
  - `alltalk_next.wav` - (may not be used in current implementation)

## Troubleshooting

### Issue: "AllTalk server returned 500"
**Solution**: Ensure AllTalk server is running and accessible on port 7851

### Issue: Page turns too early/late
**Solution**: Adjust `page_turn_buffer` in main.py:
```python
tts = AllTalkTTSService(
    # ... other params ...
    page_turn_buffer=0.2,  # Turn at 80% (earlier)
    # or
    page_turn_buffer=0.4,  # Turn at 60% (later)
)
```

### Issue: Audio generation delays
**Causes**:
- AllTalk server overloaded
- Network latency to server
- Text too long to synthesize quickly

**Solution**: 
- Reduce text length per page
- Increase `preload_ratio` in `tts_alltalk.py` `_schedule_prefetch()` to prefetch earlier

### Issue: Prefetch errors in console
**Check**: Look for messages like:
```
Prefetch error: ...
```
**Solution**: Increase the preload ratio or check AllTalk server logs

## Performance Metrics to Monitor

### Good Performance
- **TTS Generation Time**: 2-5 seconds for typical page (200-300 words)
- **Prefetch Success**: Near 100% (no "Prefetch error" messages)
- **Page Turn Timing**: Consistent delays shown in debug output

### Suboptimal Performance
- **Long TTS Generation**: > 10 seconds
  - May indicate AllTalk server bottleneck
  - Try shorter page lengths
  
- **Failed Prefetches**: Intermittent errors
  - Network issues or server overload
  - Monitor AllTalk server logs

## Advanced Customization

### Adjust Prefetch Timing
In `src/services/tts_alltalk.py`, line ~268:
```python
def _schedule_prefetch(self, next_text: str, reference_audio: Optional[str], 
                       duration: float, preload_ratio: float = 0.7):
    """Prefetch at 70% of duration (configurable)"""
    # Change 0.7 to 0.8 for later prefetch, or 0.6 for earlier
```

### Change Default Voice
In `src/main.py`:
```python
tts = AllTalkTTSService(
    voice="male_09.wav",  # or any voice available in AllTalk
)
```

### Disable Prefetching (for testing)
In `src/orchestrator.py`, comment out the prefetch call in `_play_tts_service()`:
```python
# For testing without prefetch:
# duration, page_turn_delay, playback_task = await self._play_tts_service(
#     current_text, None, reference_audio, on_time_update  # Set next_text to None
# )
```

## Files Modified

1. **src/services/tts_service.py** - Complete abstract interface
2. **src/services/tts_alltalk.py** - Already had proper implementation
3. **src/orchestrator.py** - Fixed delay and prefetch handling
4. **INTEGRATION_IMPROVEMENTS.md** - Detailed documentation (this file)

## Verification Checklist

- [ ] AllTalk server is running on port 7851
- [ ] main.py uses AllTalkTTSService
- [ ] Application starts without errors
- [ ] Console shows "✓ AllTalk TTS initialized successfully"
- [ ] Pages turn at expected timing (70% through audio)
- [ ] No "Prefetch error" messages
- [ ] Audio quality is good
- [ ] Page transitions are smooth
- [ ] No audio gaps between pages

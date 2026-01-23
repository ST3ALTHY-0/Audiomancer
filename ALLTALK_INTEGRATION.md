# AllTalk TTS Integration Guide

This guide explains how to integrate and use the AllTalk TTS service with KindleReader.

## Overview

AllTalk is an external TTS (Text-to-Speech) API server that provides high-quality voice synthesis. The KindleReader application has been integrated with AllTalk through the `AllTalkTTSService` class, which implements the standard `TTSService` interface.

## Prerequisites

### 1. Install AllTalk TTS Server

AllTalk must be running as a separate service. Follow the installation instructions at:
https://github.com/erew123/alltalk_tts

Quick start (assuming you have AllTalk installed):
```bash
python alltalk_tts.py
```

By default, AllTalk runs on `http://127.0.0.1:7851`

### 2. Verify AllTalk is Running

You should see output like:
```
INFO:     Uvicorn running on http://127.0.0.1:7851
```

### 3. Install KindleReader Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### Option 1: Use AllTalk in main.py (Simple)

Edit `src/main.py` and uncomment the AllTalk section:

```python
# Instead of this:
tts = CoquiTTSService(...)

# Use this:
tts = AllTalkTTSService(
    voice="female_06.wav",
    language="en",
    volume=100,
    rate=1.0,
    server_url="http://127.0.0.1:7851",
)
```

### Option 2: Add to config.py (Recommended)

Add these configuration variables to `src/config.py`:

```python
# AllTalk TTS Configuration
ALLTALK_ENABLED = True
ALLTALK_VOICE = "female_06.wav"      # Voice file name
ALLTALK_LANGUAGE = "en"              # Language code
ALLTALK_SERVER = "http://127.0.0.1:7851"
```

Then use in main.py:

```python
if getattr(config, 'ALLTALK_ENABLED', False):
    tts = AllTalkTTSService(
        voice=getattr(config, 'ALLTALK_VOICE', 'female_06.wav'),
        language=getattr(config, 'ALLTALK_LANGUAGE', 'en'),
        volume=int(getattr(config, 'TTS_VOLUME', 100)),
        server_url=getattr(config, 'ALLTALK_SERVER', 'http://127.0.0.1:7851'),
    )
else:
    tts = CoquiTTSService(...)
```

## Usage

### Running KindleReader with AllTalk

```bash
python src/main.py
```

### Quick Test

Test the AllTalk integration without running the full reader:

```bash
python src/main_alltalk.py test
```

This will:
1. Connect to the AllTalk server
2. Generate and play a test phrase
3. Display timing information

### Full KindleReader Session

Run the full reader with AllTalk:

```bash
python src/main_alltalk.py
```

## API Classes

### AllTalkTTSService

Main service class that implements the TTSService interface.

**Constructor Parameters:**
- `voice` (str): Voice file name (e.g., "female_06.wav")
- `language` (str): Language code (default "en")
- `volume` (int): Volume level 1-100 (default 100)
- `rate` (float): Speech rate multiplier (default 1.0)
- `server_url` (str): AllTalk server URL (default "http://127.0.0.1:7851")
- `output_dir` (str): Directory for temporary audio files (default "output/temp")
- `page_turn_buffer` (float): Timing for page turning (default 0.3)

**Key Methods:**

```python
# Initialize the service
await tts.initialize()

# Generate and play text (non-blocking with pipelining)
duration, page_turn_delay = await tts.speak(
    text="Your text here",
    next_text="Next page text (optional)",
    reference_audio=None  # Not used for AllTalk
)

# Change voice at runtime
tts.set_voice("male_01.wav")
tts.set_volume(80)
tts.set_rate(1.2)

# Wait for playback to complete
await tts.wait_for_playback()

# Cleanup resources
await tts.cleanup()
```

### allTalk_client Module

Low-level API client for communicating with AllTalk server.

**Main Functions:**

```python
# Generate audio file from text
output_path = tts_to_wav(
    text="Your text",
    output_path="/path/to/output.wav",
    voice="female_06.wav",
    language="en"
)

# Stream audio bytes (advanced)
audio_stream = stream_tts(
    text="Your text",
    voice="female_06.wav",
    language="en"
)

# Play stream using ffplay
play_stream(audio_stream)
```

## Available Voices

AllTalk comes with various voice files. Common voices include:
- `female_06.wav` - Female voice (default)
- `male_01.wav` - Male voice
- Other voices available in your AllTalk installation

Check your AllTalk server's voice directory for available options.

## Troubleshooting

### "Failed to connect to AllTalk server"

1. Verify AllTalk is running:
   ```bash
   curl http://127.0.0.1:7851/api/
   ```

2. Check the server URL in configuration matches your setup

3. Ensure no firewall is blocking port 7851

### "Voice file not found"

1. Verify the voice file exists in AllTalk's voice directory
2. Use correct filename (case-sensitive on Linux)
3. Check AllTalk logs for available voices

### "Audio playback issues"

1. Verify audio file was generated correctly
2. Check system audio settings
3. Ensure simpleaudio is installed: `pip install simpleaudio`

### "Slow performance"

1. AllTalk may be processing multiple requests
2. Check system CPU/memory usage
3. Try reducing text length per request
4. Consider using a faster voice if available

## Performance Notes

- **Startup**: AllTalk service initialization takes 5-10 seconds
- **Generation**: Audio generation time depends on text length and CPU
- **Pipelining**: The service prefetches the next page while current page plays
- **Memory**: Temporary audio files are stored in `output/temp/`

## Architecture

The integration works as follows:

1. **KindleReaderOrchestrator** calls `tts.speak(text)`
2. **AllTalkTTSService** forwards the request to `allTalk_client.tts_to_wav()`
3. **allTalk_client** sends form-data to AllTalk API server on port 7851
4. AllTalk server returns JSON with file URL
5. Client downloads the generated WAV file
6. AllTalkTTSService plays the audio using simpleaudio
7. Control returns immediately (non-blocking)
8. Next page is prefetched while current plays (pipelining)

## Comparison with Other Services

| Feature | AllTalk | Coqui | RealTime |
|---------|---------|-------|----------|
| Offline | Optional (API-based) | Yes | Yes |
| Quality | High | High | Medium |
| Speed | Moderate | Slow (CPU) | Fast |
| GPU Support | Server-side | Yes | No |
| Setup | Complex | Simple | Simple |
| Cost | Free (self-hosted) | Free | Free |

## Examples

### Basic Usage

```python
import asyncio
from services.tts_alltalk import AllTalkTTSService

async def main():
    tts = AllTalkTTSService()
    await tts.initialize()
    
    duration, delay = await tts.speak("Hello world!")
    await tts.wait_for_playback()
    await tts.cleanup()

asyncio.run(main())
```

### With Configuration

```python
tts = AllTalkTTSService(
    voice="male_01.wav",
    language="en",
    volume=85,
    rate=0.9,
    server_url="http://192.168.1.100:7851"
)
```

### Runtime Changes

```python
# Change voice mid-session
tts.set_voice("female_01.wav")

# Adjust playback speed
tts.set_rate(1.1)

# Change volume
tts.set_volume(75)
```

## Additional Resources

- AllTalk TTS: https://github.com/erew123/alltalk_tts
- KindleReader Source: See src/ directory
- TTSService Interface: [src/services/tts_service.py](src/services/tts_service.py)

## Support

For issues with:
- **AllTalk server**: See https://github.com/erew123/alltalk_tts/issues
- **KindleReader integration**: Check the main repository
- **TTS quality**: Adjust voice selection and rate settings

# allTalk_client.py
import os
import time
import sys
import requests
from typing import Iterator
import subprocess

# Client for allTalk TTS API server
# Connects to allTalk running on port 7851 for text-to-speech generation

def stream_tts(text: str, voice: str = "default", language: str = "en") -> Iterator[bytes]:
    """
    Stream allTalk audio bytes from local server on port 7851.
    """
    server_url = "http://127.0.0.1:7851"
    
    start = time.perf_counter()
    res = requests.post(
        f"{server_url}/api/tts-generate",
        data={
            "text_input": text,
            "text_filtering": "standard",
            "character_voice_gen": voice,
            "language": language,
            "output_file_name": "stream",
            "output_file_timestamp": "true",
            "narrator_enabled": "false",
            "rvccharacter_voice_gen": "Disabled",
            "autoplay": "false"
        },
        stream=True,
    )
    end = time.perf_counter()
    print(f"Time to make POST: {end-start:.3f}s", file=sys.stderr)

    if res.status_code != 200:
        raise RuntimeError(f"Error: {res.text}")

    first = True
    for chunk in res.iter_content(chunk_size=512):
        if first:
            end = time.perf_counter()
            print(f"Time to first chunk: {end-start:.3f}s", file=sys.stderr)
            first = False
        if chunk:
            yield chunk

def tts_to_wav(text: str, output_path: str = None, voice: str = "default", language: str = "en") -> str:
    """
    Get TTS audio as WAV file from allTalk server.
    Returns path to saved WAV file.
    """
    server_url = "http://127.0.0.1:7851"
    
    if output_path is None:
        output_path = f"output_{int(time.time())}.wav"
    
    # Extract filename without path for the API call
    output_file_name = os.path.splitext(os.path.basename(output_path))[0]
    
    res = requests.post(
        f"{server_url}/api/tts-generate",
        data={
            "text_input": text,
            "text_filtering": "standard",
            "character_voice_gen": voice,
            "language": language,
            "output_file_name": output_file_name,
            "output_file_timestamp": "false",
            "narrator_enabled": "false",
            "rvccharacter_voice_gen": "Disabled",
            "autoplay": "false"
        }
    )
    
    if res.status_code != 200:
        raise RuntimeError(f"Error: {res.text}")
    
    # Parse response to get file URL
    result = res.json()
    status = str(result.get('status', '')).lower()
    if status not in {"success", "generate-success", "generate_success"}:
        raise RuntimeError(f"TTS generation failed: {result}")
    
    # Download the audio file from the returned URL
    audio_response = requests.get(f"{server_url}{result['output_file_url']}")
    
    if audio_response.status_code != 200:
        raise RuntimeError(f"Failed to download audio: {audio_response.text}")
    
    # Save to the specified output path
    with open(output_path, 'wb') as f:
        f.write(audio_response.content)
    
    return output_path

def play_stream(audio_stream):
    """
    Play audio bytes from allTalk streaming endpoint in real-time.
    """
    ffplay_cmd = [
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-f", "s16le",
        "-ar", "24000",
        "-ac", "1",
        "-"
    ]

    with subprocess.Popen(ffplay_cmd, stdin=subprocess.PIPE) as proc:
        try:
            for chunk in audio_stream:
                proc.stdin.write(chunk)
        except BrokenPipeError:
            pass  # ffplay closed early
        finally:
            proc.stdin.close()
            proc.wait()
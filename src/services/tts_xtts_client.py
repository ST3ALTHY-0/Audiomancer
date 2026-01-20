# xtts_client.py
import os
import time
import sys
import requests
from typing import Iterator
import subprocess

# Not used Rn, my plan was to use this to conenct to a xtts api server running on a linux vm/docker
#So we could use deepspeed to see if we could get realtime tts/streaming, but im having problems with packages

def stream_tts(text: str, chunk_size: int = 20) -> Iterator[bytes]:
    """
    Stream XTTS V2 audio bytes from local server on port 8020.
    """
    server_url = "http://localhost:8020"
    
    start = time.perf_counter()
    res = requests.post(
        f"{server_url}/tts_stream",
        json={"text": text, "chunk_size": chunk_size},
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

def tts_to_wav(text: str, output_path: str = None) -> str:
    """
    Get TTS audio as WAV file from local server.
    Returns path to saved WAV file.
    """
    server_url = "http://localhost:8020"
    
    res = requests.post(
        f"{server_url}/tts_to_file",
        json={"text": text}
    )
    
    if res.status_code != 200:
        raise RuntimeError(f"Error: {res.text}")
    
    if output_path is None:
        output_path = f"output_{int(time.time())}.wav"
    
    with open(output_path, 'wb') as f:
        f.write(res.content)
    
    return output_path

def play_stream(audio_stream):
    """
    Play audio bytes from XTTS streaming endpoint in real-time.
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
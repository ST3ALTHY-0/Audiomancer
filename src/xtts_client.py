# xtts_client.py
import os
import time
import sys
import requests
from typing import Iterator

# Example text streaming generator
def stream_tts(text: str, model_id: str, chunk_size: int = 20) -> Iterator[bytes]:
    """
    Stream XTTS V2 audio bytes from Baseten endpoint.
    """
    baseten_api_key = os.environ.get("BASETEN_API_KEY")
    if not baseten_api_key:
        raise RuntimeError("Set BASETEN_API_KEY environment variable")

    start = time.perf_counter()
    res = requests.post(
        f"https://model-{model_id}.api.baseten.co/development/predict",
        headers={"Authorization": f"Api-Key {baseten_api_key}"},
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

# xtts_client.py (continued)
import subprocess

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


# import os

# # MUST be set before importing TTS
# os.environ["PHONEMIZER_ESPEAK_PATH"] = r"C:\Program Files\eSpeak NG\espeak-ng.exe"
import torch
import simpleaudio as sa
from TTS.api import TTS

device = "cuda" if torch.cuda.is_available() else "cpu"

print(TTS().list_models())

tts = TTS("tts_models/en/vctk/vits").to(device)

print(tts.speakers)


tts.tts_to_file(
    text="Speaking now",
    speaker="p229",
    file_path="out.wav",
    
)

wave = sa.WaveObject.from_wave_file("out.wav")
wave.play().wait_done()

import requests

url = "http://127.0.0.1:8020/tts_to_file"

speaker_wav = r"C:\Programming\Python\kindleReader\src\voices\samples\777-126732-0028.wav"
output_wav = "output.wav"

with open(speaker_wav, "rb") as f:
    response = requests.post(
        url,
        files={"speaker_wav": f},
        data={
            "text": "Hello! This is a test using the XTTS server without streaming.",
            "language": "en"
        }
    )

response.raise_for_status()

with open(output_wav, "wb") as out:
    out.write(response.content)

print("Saved:", output_wav)

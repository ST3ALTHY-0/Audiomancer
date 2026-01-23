import requests
import io
from pydub import AudioSegment
from pydub.playback import play

text = """“What’s your name?” he whispered. “Aliya,” she said softly. “Aliya, if you make a sound before I’m gone from this house, I’ll be back here before any of your father’s guards can reach you. You won’t like it if that happens. Do you understand?” She nodded. But she continued to stare at him. Her eyes moved over his black form, as if she was trying to determine what he was. The fear was slowly being replaced by something else. “The safest thing for you,” he said, “is to return to your dreams and forget me.” He needed to get out of the house. But the sight of her held him there. He’d always had a taste for pretty elves with golden hair. She stared at him. Not moving, not making a sound. He drew off one of his gloves and reached out slowly. She watched his hand, but didn’t react as he cupped one of her plump breasts. He thumbed the nipple until it stiffened. Still she did nothing to stop him. Her eyes swelled, and he grinned behind his mask. “You like that, do you?” Her voice quavered as he continued stimulating her. “It feels very strange,” she said softly. She made no move to interrupt him. It was as if she had no idea what

Dalton, Michael. Master of Thieves: The Complete Series (pp. 11-12). Kindle Edition. """

# Custom output path
output_path = r"C:\Programming\Python\kindleReader\output\temp\testOutput.wav"

response = requests.post(
    "http://127.0.0.1:7851/api/tts-generate",
    data={
        "text_input": text,
        "text_filtering": "standard",
        "character_voice_gen": "female_06.wav",
        "language": "en",
        "output_file_name": "testOutput",
        "output_file_timestamp": "false",
        "narrator_enabled": "false",
        "rvccharacter_voice_gen": "Disabled",
        "autoplay": "false"
    }
)

# Get the audio file path from response
result = response.json()
print(f"Status: {result['status']}")
print(f"File URL: {result['output_file_url']}")

# Download the generated audio
audio_response = requests.get(f"http://127.0.0.1:7851{result['output_file_url']}")

# Save to custom path
with open(output_path, 'wb') as f:
    f.write(audio_response.content)
print(f"Audio saved to: {output_path}")

# Play the audio
audio = AudioSegment.from_file(io.BytesIO(audio_response.content))
play(audio)
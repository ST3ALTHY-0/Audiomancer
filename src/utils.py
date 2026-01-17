import os
import sys
import json
import asyncio
from dataclasses import dataclass, asdict
from config import *
# Avoid circular import: import start_tts_server_once lazily inside get_voice_list


def resource_path(rel_path):
    """Get absolute path for PyInstaller or normal run."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


######################## Get/Load Voices from server ##############################


def load_voices(path: str = VOICES_FILE) -> 'VoiceStore':
    """Load persisted voices from the local voices file. Returns VoiceStore."""
    store = VoiceStore()
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                v = Voice(index=item.get('index', 0), name=item.get('name', ''), locale=item.get('locale', ''), raw=item.get('raw', ''))
                store.add(v)
    except Exception as e:
        print(f"Failed to load voices from {path}: {e}")
    return store


@dataclass
class Voice:
    index: int
    name: str
    locale: str = ''
    raw: str = ''


class VoiceStore:
    def __init__(self):
        self.voices = []  # list[Voice]

    def add(self, v: Voice):
        self.voices.append(v)

    def to_list(self):
        return [asdict(v) for v in self.voices]

    def save(self, path: str = VOICES_FILE):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_list(), f, ensure_ascii=False, indent=2)


async def get_voice_list(timeout: float = 2.0) -> VoiceStore:
    """Query the TTS server for available voices, parse and persist them.

    Returns a VoiceStore instance.
    """
    store = VoiceStore()
    if not TTS_USE_TCP:
        return store

    try:
        from old.kindleReader import start_tts_server_once
        await start_tts_server_once()
    except Exception:
        # if the function isn't available or import fails, continue — server auto-start is optional
        pass
    try:
        reader, writer = await asyncio.open_connection(TTS_SERVER_HOST, TTS_SERVER_PORT)
        writer.write(("list-voices" + "\n").encode("utf-8"))
        await writer.drain()

        # Read responses until EOF or timeout
        lines = []
        try:
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=timeout)
                if not line:
                    break
                decoded = line.decode('utf-8', errors='replace').strip()
                if decoded:
                    lines.append(decoded)
        except asyncio.TimeoutError:
            # timeout reading more lines — proceed with what we have
            pass

        # close writer
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        # Parse lines like: Voice[0]: Microsoft David Desktop - English (United States)
        import re
        m_re = re.compile(r"Voice\[(\d+)\]:\s*(.+)")
        for ln in lines:
            m = m_re.match(ln)
            if not m:
                continue
            idx = int(m.group(1))
            label = m.group(2).strip()
            # split name and locale by ' - ' if present
            if ' - ' in label:
                name, locale = label.split(' - ', 1)
            else:
                name, locale = label, ''
            v = Voice(index=idx, name=name.strip(), locale=locale.strip(), raw=label)
            store.add(v)

        # Persist the discovered voices
        try:
            store.save()
        except Exception as e:
            print(f"Failed to save voices to {VOICES_FILE}: {e}")

        return store
    except Exception as e:
        print(f"TTS TCP send/read error: {e}")
        return store


def remove_contractions(text: str) -> str:
    """Remove common English contractions from text."""
    import re
    
    # First pass: specific common contractions
    contractions_dict = {
        "ain't": "am not",
        "aren't": "are not",
        "can't": "cannot",
        "can't've": "cannot have",
        "could've": "could have",
        "couldn't": "could not",
        "didn't": "did not",
        "doesn't": "does not",
        "don't": "do not",
        "hadn't": "had not",
        "hasn't": "has not",
        "haven't": "have not",
        "he'd": "he would",
        "he'll": "he will",
        "he's": "he is",
        "how'd": "how did",
        "how'll": "how will",
        "how's": "how is",
        "i'd": "i would",
        "i'll": "i will",
        "i'm": "i am",
        "i've": "i have",
        "isn't": "is not",
        "it'd": "it would",
        "it'll": "it will",
        "it's": "it is",
        "let's": "let us",
        "shouldn't": "should not",
        "that's": "that is",
        "there's": "there is",
        "they'd": "they would",
        "they'll": "they will",
        "they're": "they are",
        "they've": "they have",
        "wasn't": "was not",
        "we'd": "we would",
        "we'll": "we will",
        "we're": "we are",
        "we've": "we have",
        "weren't": "were not",
        "what's": "what is",
        "won't": "will not",
        "wouldn't": "would not",
        "you'd": "you would",
        "you'll": "you will",
        "you're": "you are",
        "you've": "you have",
    }
    
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in contractions_dict.keys()) + r")\b", re.IGNORECASE)
    result = pattern.sub(lambda m: contractions_dict[m.group(0).lower()], text)
    
    # Second pass: general contraction patterns for any word
    # 's -> is (but avoid possessives by checking context - if followed by space + lowercase, likely "is")
    result = re.sub(r"(\w+)'s\b", lambda m: m.group(1) + " is", result)
    
    # 're -> are
    result = re.sub(r"(\w+)'re\b", lambda m: m.group(1) + " are", result)
    
    # 've -> have
    result = re.sub(r"(\w+)'ve\b", lambda m: m.group(1) + " have", result)
    
    # 'll -> will
    result = re.sub(r"(\w+)'ll\b", lambda m: m.group(1) + " will", result)
    
    # 'd -> would
    result = re.sub(r"(\w+)'d\b", lambda m: m.group(1) + " would", result)
    
    # n't -> not (catch-all for any remaining negatives)
    result = re.sub(r"(\w+)n't\b", lambda m: m.group(1) + " not", result)
    
    # 'm -> am
    result = re.sub(r"(\w+)'m\b", lambda m: m.group(1) + " am", result)
    
    return result
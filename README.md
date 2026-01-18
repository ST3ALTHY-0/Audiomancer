# Kindle Reader TTS

A Windows utility that uses OCR to extract text from the Kindle app and reads it aloud using local TTS engines with natural-sounding voices. Features synchronized page turning and smart audio prefetching for seamless reading.

## Features

- **Smart OCR Integration**: Captures text from Kindle Windows app using Tesseract OCR
- **Multiple TTS Engines**: 
  - Coqui TTS (VCTK/VITS) - Fast, pretrained models with good quality
  - XTTS v2 - Custom voice cloning with streaming support
  - gTTS - Fast fallback option
- **Synchronized Reading**: Page turns automatically sync with spoken audio
- **Smart Prefetching**: Generates next page audio while current page plays for seamless transitions
- **Contraction Handling**: Automatically expands contractions for better VITS pronunciation
- **Background Operation**: Works with Kindle in background (window must be visible, not minimized)
- **GPU Acceleration**: CUDA support for faster TTS generation on compatible GPUs

## Quick Start

### 1. Install Prerequisites

**Python 3.11+** (recommended)

**Tesseract OCR**:
- Download from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)
- Note installation path (default: `C:\Program Files\Tesseract-OCR`)

**Python Packages**:
```cmd
# Create virtual environment (recommended)
python -m venv venv311
venv311\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Tesseract Path

Edit `src/config.py` and set the Tesseract path:
```python
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 3. Download TTS Models

**For Coqui VCTK (recommended for beginners)**:
Models download automatically on first run.

**For XTTS (voice cloning)**:
1. Models download automatically
2. Place reference voice samples in `speakers/` directory
3. Samples should be clear, 6-12 seconds of speech

### 4. Run the Application

```cmd
python src/main.py
```

## Usage

1. **Start Application**: Launch `src/main.py`
2. **Select TTS Engine**: Choose from dropdown (Coqui TTS, XTTS, or Fast TTS)
3. **Configure Voice**: 
   - VCTK: Select speaker from dropdown (p254, p376, etc.)
   - XTTS: Select reference audio file
4. **Adjust Settings**:
   - Speed: 0.5x to 2.0x
   - Volume: 1-100%
5. **Set Crop Region**: Click "Set Crop" to define text capture area
6. **Start Reading**: Click "Start" and use Kindle normally

### Keyboard Controls

- **Start/Stop**: Click button or use GUI
- **Page Navigation**: Use Kindle's native controls
- **Audio stops automatically** when you stop reading

## TTS Engine Comparison

| Engine | Speed | Quality | GPU Required | Voice Options | Best For |
|--------|-------|---------|--------------|---------------|----------|
| **Coqui VCTK** | Fast (real-time) | Good | Optional | ~100 pretrained voices | General reading |
| **Coqui VITS** | Fast (real-time) | Good | Optional | ~100 pretrained voices | General reading |
| **XTTS v2** | Slower (prefetch helps) | Excellent | Recommended | Custom voice cloning | Specific voice preference |
| **gTTS** | Very fast | Basic | No | Google voices | Quick testing |

## Advanced Features

### Smart Contraction Handling

VITS models struggle with contractions. The app automatically:
- Detects and expands contractions ("he'd" → "he would")
- Handles possessives correctly ("mind's eye" → "minds eye")
- Distinguishes "has" vs "is" ("he's finished" → "he has finished")
- Supports curly apostrophes from Kindle

### Audio Prefetching

- Generates next page audio at ~70% of current playback
- Page turns at ~72% to start OCR preprocessing
- Near-instant transitions between pages
- No overlapping audio

### GPU Acceleration

If you have an NVIDIA GPU with CUDA:
```cmd
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

The app auto-detects CUDA and uses GPU acceleration for faster generation.

## Configuration

Key settings in `src/config.py`:

```python
# OCR
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
CROP_LEFT = 100    # Adjust to your screen
CROP_TOP = 100
CROP_RIGHT = 900
CROP_BOTTOM = 700

# TTS
TTS_MODEL = "tts_models/en/vctk/vits"
TTS_VOICE = "p254"  # Default voice
```

## Troubleshooting

### "Kindle window not found"
- Ensure Kindle app is open and visible (not minimized)
- Window title should contain "Kindle"

### Poor OCR Quality
- Click "Set Crop" and adjust the region to capture only text
- Avoid page numbers, headers, images
- Ensure Kindle window is not too small

### Slow TTS Generation
- Use VCTK/VITS instead of XTTS for faster generation
- Enable GPU acceleration if available
- Close other GPU-intensive applications

### Contractions Sound Wrong
- Ensure you're using Coqui VITS (contraction expansion is automatic)
- Check that the text displays correctly in the GUI

### Page Turns Too Early/Late
- Adjust timing in `src/orchestrator.py` (line ~115):
  ```python
  turn_delay = max(0.1, duration * 0.72)  # Adjust 0.72 (72%)
  ```

## Development

### Project Structure
```
kindleReader/
├── src/
│   ├── main.py              # Entry point
│   ├── gui.py               # Tkinter GUI
│   ├── orchestrator.py      # Main reading loop & timing
│   ├── config.py            # Configuration
│   ├── controllers/         # Kindle window control
│   ├── services/            # OCR, TTS, screen capture
│   └── voices/              # Voice configurations
├── models/                  # TTS models (auto-downloaded)
├── speakers/                # Reference audio for XTTS
└── requirements.txt
```

### Key Files
- `orchestrator.py`: Controls page turn timing and audio sync
- `services/tts_python.py`: Coqui TTS implementation with contraction handling
- `services/ocr_service.py`: Tesseract OCR wrapper
- `controllers/kindle_controller.py`: Kindle window automation

## Known Issues

- XTTS is slower than real-time without GPU acceleration
- Window must remain visible (can be mostly off-screen)
- First page may have slight delay while model loads

## Requirements

- Windows 10/11
- Python 3.11+
- 4GB+ RAM (8GB+ recommended for XTTS)
- NVIDIA GPU with CUDA (optional, but recommended for XTTS)

## License

GNU General Public License v3.0 (GPL-3.0)

## Credits

- Coqui TTS for open-source TTS models
- Tesseract OCR for text recognition
- Original TTS engine integration (submodule)

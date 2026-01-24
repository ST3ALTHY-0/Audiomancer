# Audiomancer - Text-to-Speech Reader

A Windows utility that uses OCR to extract text from any window and reads it aloud using local TTS engines with natural-sounding voices. Features synchronized page/content turning and audio prefetching for continuous reading.

## Features

- **OCR Integration**: Captures text from any window using Tesseract OCR
- **Multiple TTS Engines**: 
  - Coqui TTS (VCTK/VITS) - Fast, pretrained models with good quality
  - XTTS v2 - Custom voice cloning with streaming support
  - gTTS - Fast fallback option
  - AllTalk - Local server with many engines and options
- **Synchronized Reading**: Content turns automatically sync with spoken audio
- **Prefetching**: Generates next page audio while current page plays for seamless transitions
- **Background Operation**: Works with any window in background (window must be visible, not minimized)
- **GPU Acceleration**: CUDA support for faster TTS generation on compatible GPUs

## TODO
- allow user to customize what buttons are pressed and when (save in userSetting config)
- make the gTTS page turning/timing better
- figure out/implement streaming audio
- maybe split text into sentences before sending it to TTS
- clean up files

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

**Install AllTalk TTS (if you want more TTS options)**
Alltalk has a lot of engines and custom options, very nice
only have xtts_v2 working for now, but I plan on adding some of the other engines. 

### 4. Run the Application

```cmd
python src/gui.py
```

## Usage

1. **Start Application**: Launch `src/gui.py`
2. **Select Target Window**: Open the window containing text you want to read
3. **Select TTS Engine**: Choose from dropdown (Coqui TTS, XTTS, or Fast TTS)
4. **Configure Voice**: 
   - VCTK/VITS: Select speaker from dropdown (p254, p376, etc.)
   - XTTS: Select reference audio file
5. **Adjust Settings**:
   - Speed: 0.5x to 2.0x
   - Volume: 1-100%
6. **Set Crop Region**: Click "Set Crop" to define text capture area
7. **Start Reading**: Click "Start" and navigate content normally

### Keyboard Controls

- **Start/Stop**: Click button or use GUI
- **Content Navigation**: Use native controls in your application
- **Audio stops automatically** when you stop reading


### Audio Prefetching

- Generates next page/section audio at ~70% of current playback
- Content advances at ~72% to start OCR preprocessing
- Near-instant transitions between pages
- No overlapping audio

### GPU Acceleration

If you have an NVIDIA GPU with CUDA:
```cmd
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

The app auto-detects CUDA and uses GPU acceleration for faster generation.

Tested with 2.5 but other version likely work


### Slow TTS Generation
- Use VCTK/VITS instead of XTTS for faster generation
- Enable GPU acceleration if available
- Close other GPU-intensive applications

### Contractions Sound Wrong
- Ensure you're using Coqui VITS (contraction expansion is automatic)
- Check that the text displays correctly in the GUI

## Development

### Key Files
- `orchestrator.py`: Controls content navigation timing and audio sync
- `services/tts_python.py`: Coqui TTS implementation with contraction handling
- `services/ocr_service.py`: Tesseract OCR wrapper
- `controllers/window_controller.py`: Window automation and control

## Known Issues

- XTTS is slower than real-time without GPU acceleration (Xtts works with Alltalk, but is GPU heavy)
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

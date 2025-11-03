# KindleReader TTS

Small utility to OCR text from the Kindle Windows app and read it aloud using a local TTS engine, so we can get natural sounding TTS instead of robotic trash.

Features
- Capture Kindle window text via Tesseract OCR
- Play spoken audio via a local TTS application (configurable)
- Designed for Windows (uses Win32 / pywinauto background capture)
- Kindle can be in the background, but can not be minimized in order for
the screen capture to work

Quick start

1. Install prerequisites

 - Install Python 3.8+
 - Install Tesseract OCR for Windows and note the install path (default: `C:\Program Files\Tesseract-OCR`).
 - Install Python packages (probably  want to do this inside a virtualenv):

```cmd
python -m pip install --upgrade pip
pip install pillow pytesseract pygetwindow pywinauto pyttsx3 p 
# If you use parts of the code that require win32:
pip install pywin32
```

2. Configure

- Verify `pytesseract.pytesseract.tesseract_cmd` in `kindleReader.py` points to your `tesseract.exe` path.

3. Run

Open Kindle (Windows app) and put it on a readable page, then run:

```cmd
python kindleReader.py
```

Troubleshooting
- If you see Tesseract errors mentioning "LEAK" or crashes, avoid running OCR concurrently and confirm your Tesseract installation and `tessdata` files are correct. The code serializes OCR calls but you can also test Tesseract separately.
- If TTS playback blocks Ctrl+C, the code uses an async playback worker; if you have a blocking external TTS binary, consider replacing it with the Azure Speech SDK or another non-blocking TTS engine.
- Debug images are saved as `kindle_debug_<timestamp>.png` in the working directory to help reproduce OCR issues.

Notes
- This project is Windows-oriented and uses Win32 APIs for background capture. Behavior on other OSes is not tested.
- Keep secrets (API keys) out of source control. Add `.env` to `.gitignore`.

TTS engine
----------------------------------

This project relies on an external native TTS application that provides the actual speech synthesis through editing the SAPI5 engine and editing some registry keys among other things.

Key points
- The Python wrapper expects the native TTS executable path to be available (either configured inside `kindleReader.py` or via an environment variable `TTS_EXE`).

Typical setup
1. Initialize submodules after cloning:

```cmd
git submodule init
git submodule update --recursive
```

2. Build the native TTS engine
- Open the TTS engine folder (the submodule) and follow its README — on Windows this usually means opening the supplied Visual Studio solution or running CMake to produce an x64 build.
- Ensure you build the application configuration you want (Debug/Release) and note the produced executable path (for example: `.../ttsapplication/x64/Debug/TtsApplication.exe`).

3. Configure the Python script to find the executable
- Option A: set an environment variable (recommended)

```cmd
setx TTS_EXE "C:\full\path\to\TtsApplication.exe"
```

- Option B: edit `kindleReader.py` and set `TTS_EXE` to the built executable path near the top of the file.

Runtime notes
- The Python code launches the native TTS process asynchronously so audio playback can be cancelled (Ctrl+C) while speaking. If you change the TTS engine, keep that behavior in mind.
- If the TTS engine uses additional runtime DLLs (e.g. Visual C++ redistributable), make sure those are installed on the target machine.

Troubleshooting
- If Python fails to start the TTS exe, verify the `TTS_EXE` path and that the binary is built for x64 (or the same bitness as your Python interpreter/process).
- If audio playback hangs or doesn't stop on Ctrl+C, confirm the TTS exe responds to SIGTERM/kill or update the Python wrapper to use a different child termination strategy.


License
GNU General Public License (GPL)
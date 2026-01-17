# KindleReader TTS

Small utility to OCR text from the Kindle Windows app and read it aloud using a local TTS engine, so we can get natural sounding TTS instead of robotic trash.

Features
- Capture Kindle window text via Tesseract OCR
- Play spoken audio via a local TTS application (configurable)
- Designed for Windows (uses Win32 / pywinauto background capture)
- Kindle can be in the background and the program will not focus it or interrupt your system in any way, but it can not be minimized in order for
the screen capture to work (You can drag the tab so far down that you can only see a very small portion of the window though)

Quick start

1. Install prerequisites
 - Install Python 3.8+ (I used 3.11)
 - Install Tesseract OCR for Windows and note the install path (default: `C:\Program Files\Tesseract-OCR`).
 - Install Python packages (you probably want to do this inside a virtualenv):
```cmd
# Upgrade pip
python -m pip install --upgrade pip

# Install runtime dependencies (recommended inside a virtualenv)
python -m pip install pywinauto pygetwindow pywin32 pillow pytesseract
```

or install with:
```cmd
python -m pip install -r requirements.txt
```

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
- NOTE: Feel free to change my absolute path to relative or don't use at all if you have a path variable. I just cant get my path variables working rn.

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


//new 
Using the VCTK is the easiest, due to it being a pretained model, and it can generate text faster than it is spoken. 

Xtts can have any 'voice' but is a work in progress because it only works well with deepspeed a mostly linux library (can be used with windows, but it requires specific steps to do so). but as of now Xtts takes longer to generate speech than it takes to ouput it, 290sec to gen and 270 to speek, as well as using 60+ percent of my 3090 so it isnt greatly useful rn


License
GNU General Public License (GPL)
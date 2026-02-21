# An offline music player with real-time tempo and pitch shifting
## Check the Releases page for the latest build

## Building the Executable from Source
### Requirements
[FFmpeg](https://www.ffmpeg.org)

[Python 3.13.5](https://www.python.org/downloads/release/python-3135/)

### Instructions
Put your ffmpeg executable at the root of your project folder
```
   git clone https://github.com/baleanumatthew/offline-music-player-py
   python -m venv env
   pip install -r requirements.txt
   pip install pyinstaller
   python -m PyInstaller --noconfirm --clean --onedir  --windowed --add-binary="ffmpeg.exe:." --add-binary="env/Lib/site-packages/_sounddevice_data/portaudio-binaries/libportaudio64bit.dll:_sounddevice_data/portaudio-binaries"   main.py
```
Alternatively, you can just build the project in the dev branch like this:
```
   git clone https://github.com/baleanumatthew/offline-music-player-py
   git checkout dbg
   python -m venv env
   pip install -r requirements.txt
   python ./main.py
```
   

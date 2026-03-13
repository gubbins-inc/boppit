# Bop-It SPIKE Prime — Linux / Steam Deck

A Python game controller for the LEGO SPIKE Prime hub.
Ported from Windows to Linux / WSL2 / SteamOS.

---

## Requirements

- Python 3.10 or later
- LEGO SPIKE Prime hub (Firmware 3.6)
- USB connection to hub

---

## Installation

```bash
cd ~/boppit_linux
pip install -r requirements.txt
```

On Linux you must be in the `dialout` group to access serial ports:

```bash
sudo usermod -aG dialout $USER
# Log out and back in for the change to take effect
```

---

## Serial Port Configuration

The game auto-detects the SPIKE Prime hub serial port.

Detection order:
1. `BOPIT_SERIAL_PORT` environment variable (manual override)
2. Port with LEGO/SPIKE keyword in description
3. First `/dev/ttyACM*` device
4. First `/dev/ttyUSB*` device

### Manual override

```bash
BOPIT_SERIAL_PORT=/dev/ttyACM0 python main.py
```

### WSL2 note

WSL2 does not expose USB devices natively.
You must forward the hub using **usbipd-win** on the Windows host:

```powershell
# On Windows (PowerShell as Administrator)
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

Then in WSL2:

```bash
ls /dev/ttyACM*   # confirm device appears
BOPIT_SERIAL_PORT=/dev/ttyACM0 python main.py
```

---

## Running

```bash
python main.py
```

---

## Asset Directory

Audio and video assets must be in:

```
boppit_audio_assets/
    bip/
    bop/
    endgame/
    fx/
    leave/
    ready/
    scores_ranged/
    scoresnamed/
    shake/
    themetune.mp3
    twist/
    untwist/
    background.mp4
    highscore_celebrate/
    highscore_trumpet/
    highscore_voice/
```

Windows `Zone.Identifier` metadata files are automatically ignored.

---

## Project Structure

```
boppit_linux/
    main.py                  # Entry point
    requirements.txt
    README_LINUX.md
    PORTING_PROGRESS.md
    boppit/
        __init__.py
        config.py            # Paths and constants
        asset_loader.py      # Asset scanning (Zone.Identifier safe)
        serial_interface.py  # Serial auto-detection and hub upload
        hub_code.py          # MicroPython hub firmware
        audio.py             # AudioManager
        game.py              # BopItGame, VideoPlayer, VisualTimer
    boppit_audio_assets/     # Audio/video assets (do not modify)
```

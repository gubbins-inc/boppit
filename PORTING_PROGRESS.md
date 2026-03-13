# Bop-It Linux Port — Progress Log

---

## M1 — Asset Path Refactor

**Status:** COMPLETE

**Objective:** Replace all hardcoded Windows paths with portable pathlib paths.

**Tasks**
- [x] Remove `AUDIO_ROOT = r"D:\boppit_audio"` and `VIDEO_PATH = r"D:\boppit_audio\background.mp4"`
- [x] Implement `BASE_DIR = Path(__file__).parent.parent` in `boppit/config.py`
- [x] Implement `ASSET_DIR = BASE_DIR / "boppit_audio_assets"`
- [x] Replace all `os.path.join` calls with pathlib `/` operator
- [x] Replace `os.path.exists` with `.exists()`
- [x] Replace `open(HIGHSCORE_FILE)` with `HIGHSCORE_FILE.open()`

**Validation**
Program references no absolute paths. All asset access is via `ASSET_DIR` in `config.py`.

**Notes**
Original asset directory name is `boppit_audio_assets/`, not `boppit_audio/` as assumed in Windows version.

---

## M2 — Zone.Identifier Filtering

**Status:** COMPLETE

**Objective:** Prevent loading of Windows Zone.Identifier metadata files on Linux.

**Tasks**
- [x] Add `:` check in `asset_loader.list_audio_files()`
- [x] Add `:` check in `audio.AudioManager.play_fx()`
- [x] Confirmed `background.mp4:Zone.Identifier` present in assets — not loaded

**Validation**
`list_audio_files()` filters any filename containing `:`. Only `.mp3` files without `:` are returned.

---

## M3 — Serial Port Auto-Detection

**Status:** COMPLETE

**Objective:** Replace `SERIAL_PORT = 'COM3'` with automatic Linux serial detection.

**Tasks**
- [x] Implement `detect_spike_port()` in `boppit/serial_interface.py`
- [x] Priority 1: `BOPIT_SERIAL_PORT` environment variable
- [x] Priority 2: Port description matching SPIKE/LEGO keywords
- [x] Priority 3: `/dev/ttyACM*` fallback
- [x] Priority 4: `/dev/ttyUSB*` fallback
- [x] Priority 5: `COM*` port (Windows compatibility)
- [x] Graceful failure with diagnostic message including available ports and dialout group hint
- [x] Implement `connect()` and `upload_hub_code()` in `serial_interface.py`

**Validation**
On failure: clear error message printed to stderr. On success: port logged to stdout.

---

## M4 — Code Modularisation

**Status:** COMPLETE

**Objective:** Split monolith `bop_it_pro_2.py` into isolated modules.

**Tasks**
- [x] `boppit/config.py` — paths and constants
- [x] `boppit/asset_loader.py` — filesystem scanning with Zone.Identifier filtering
- [x] `boppit/serial_interface.py` — serial detection, connection, hub upload
- [x] `boppit/hub_code.py` — MicroPython hub firmware string
- [x] `boppit/audio.py` — AudioManager using pathlib
- [x] `boppit/game.py` — BopItGame, VideoPlayer, VisualTimer (logic unchanged)
- [x] `main.py` — entry point at project root

**Validation**
`python main.py` is the single run command. Platform-specific code is isolated to `config.py` and `serial_interface.py`.

---

## M5 — Dependencies

**Status:** COMPLETE

**Objective:** Document and pin all required Python packages.

**Tasks**
- [x] Inspect imports: `pygame`, `pyserial`, `opencv-python`, `Pillow`
- [x] Write `requirements.txt`

**Validation**
`pip install -r requirements.txt` installs all dependencies.

---

## M6 — Documentation

**Status:** COMPLETE

**Objective:** Provide Linux installation and run instructions.

**Tasks**
- [x] Write `README_LINUX.md` with installation, serial config, and run instructions

---

## Completion Checklist

| Criterion                         | Status  |
|-----------------------------------|---------|
| No Windows path references        | DONE    |
| Audio assets load via pathlib     | DONE    |
| Zone.Identifier files ignored     | DONE    |
| Serial auto-detection implemented | DONE    |
| Graceful serial failure           | DONE    |
| Game logic unchanged              | DONE    |
| Modular structure                 | DONE    |
| requirements.txt                  | DONE    |
| README_LINUX.md                   | DONE    |

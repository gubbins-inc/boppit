from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ASSET_DIR = BASE_DIR / "boppit_audio_assets"
VIDEO_PATH = ASSET_DIR / "background.mp4"
ACTIONS_IMAGE_PATH = ASSET_DIR / "actions.png"
HIGHSCORE_FILE = BASE_DIR / "highscore.json"

BAUD_RATE = 115200

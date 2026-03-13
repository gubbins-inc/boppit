import random
from pathlib import Path


def list_audio_files(folder: Path) -> list[Path]:
    """Return .mp3 files in folder, filtering out Zone.Identifier and other invalid names."""
    if not folder.exists():
        return []
    return [
        f for f in folder.iterdir()
        if f.suffix == ".mp3" and ":" not in f.name
    ]


def random_audio_file(folder: Path) -> Path | None:
    files = list_audio_files(folder)
    return random.choice(files) if files else None


def validate_assets(asset_dir: Path) -> dict:
    """Scan asset directory and report status. Returns dict with counts and warnings."""
    results = {"folders": {}, "warnings": []}

    if not asset_dir.exists():
        results["warnings"].append(f"Asset directory not found: {asset_dir}")
        return results

    for item in sorted(asset_dir.iterdir()):
        if ":" in item.name:
            results["warnings"].append(f"Skipping invalid file: {item.name}")
            continue
        if item.is_dir():
            mp3_files = list_audio_files(item)
            results["folders"][item.name] = len(mp3_files)

    return results

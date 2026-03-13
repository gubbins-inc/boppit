import time
import pygame
from pathlib import Path

from .asset_loader import list_audio_files, random_audio_file
from .config import ASSET_DIR


class AudioManager:
    def __init__(self):
        pygame.mixer.init()
        pygame.mixer.set_reserved(3)
        self.sfx_channel = pygame.mixer.Channel(1)
        self.voice_channel = pygame.mixer.Channel(2)
        self.music_channel = pygame.mixer.Channel(3)

        self.sfx_channel.set_volume(1.0)
        self.voice_channel.set_volume(0.6)

    def _play_random_from_folder(self, folder: Path, channel: pygame.mixer.Channel) -> None:
        path = random_audio_file(folder)
        if path:
            channel.play(pygame.mixer.Sound(str(path)))

    def start_music(self) -> None:
        path = ASSET_DIR / "themetune.mp3"
        if path.exists():
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(0.05)
            pygame.mixer.music.play(-1)

    def stop_music(self) -> None:
        pygame.mixer.music.stop()

    def play_fx(self, action: str) -> None:
        filename_map = {
            "BOP": "bopped.mp3",
            "BIP": "bipped.mp3",
            "TWIST": "twisted.mp3",
            "UNTWIST": "untwisted.mp3",
            "SHAKE": "shook.mp3",
            "LEAVE": "left.mp3",
        }
        filename = filename_map.get(action)
        if filename:
            path = ASSET_DIR / "fx" / filename
            if path.exists() and ":" not in path.name:
                self.sfx_channel.play(pygame.mixer.Sound(str(path)))

    def play_ready(self) -> None:
        self._play_random_from_folder(ASSET_DIR / "ready", self.voice_channel)

    def play_command(self, action: str) -> None:
        self._play_random_from_folder(ASSET_DIR / action.lower(), self.voice_channel)

    def play_game_over_comment(self, score: int) -> None:
        self.stop_music()
        if score <= 10:
            subfolder = "insult"
        elif score <= 30:
            subfolder = "encourage"
        elif score <= 50:
            subfolder = "neutral"
        else:
            subfolder = "welldone"
        self._play_random_from_folder(ASSET_DIR / "endgame" / subfolder, self.sfx_channel)

    def play_endgame_sequence(self, score: int, is_highscore: bool, on_complete_callback) -> None:
        time.sleep(0.1)
        while self.sfx_channel.get_busy():
            time.sleep(0.1)
        time.sleep(0.2)

        if 0 <= score <= 50:
            path = ASSET_DIR / "scoresnamed" / f"{score}.mp3"
        else:
            if 51 <= score <= 60:
                filename = "51-60.mp3"
            elif 61 <= score <= 70:
                filename = "61-70.mp3"
            elif 71 <= score <= 80:
                filename = "71-80.mp3"
            elif 81 <= score <= 90:
                filename = "81-90.mp3"
            elif 91 <= score <= 100:
                filename = "91-100.mp3"
            elif 101 <= score <= 150:
                filename = "101-150.mp3"
            elif 151 <= score <= 200:
                filename = "151-200.mp3"
            elif 201 <= score <= 250:
                filename = "201-250.mp3"
            else:
                filename = "251-999.mp3"
            path = ASSET_DIR / "scores_ranged" / filename

        if path.exists():
            self.voice_channel.play(pygame.mixer.Sound(str(path)))

        if is_highscore:
            time.sleep(0.1)
            while self.voice_channel.get_busy():
                time.sleep(0.1)
            self._play_random_from_folder(ASSET_DIR / "highscore_trumpet", self.sfx_channel)
            time.sleep(0.1)
            while self.sfx_channel.get_busy():
                time.sleep(0.1)
            self.sfx_channel.set_volume(0.2)
            self._play_random_from_folder(ASSET_DIR / "highscore_celebrate", self.sfx_channel)
            self._play_random_from_folder(ASSET_DIR / "highscore_voice", self.voice_channel)
            time.sleep(0.1)
            while self.sfx_channel.get_busy():
                time.sleep(0.1)
            self.sfx_channel.set_volume(1.0)

        if on_complete_callback:
            on_complete_callback()

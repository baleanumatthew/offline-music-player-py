import time
import pygame
from dataclasses import dataclass
from typing import Optional
from mutagen._file import File as MutagenFile

@dataclass
class TrackInfo:
    path: str
    duration_s: float


class AudioEngine:
    def __init__(self):
        pygame.mixer.init()
        self._track: TrackInfo | None = None

        self._is_playing = False
        self._is_paused = False

        self._offset_s = 0.0            
        self._start_mono = 0.0          

    def load(self, path: str) -> TrackInfo:
        duration = self._get_duration(path)
        pygame.mixer.music.load(path)

        self._track = TrackInfo(path=path, duration_s=duration)
        self._is_playing = False
        self._is_paused = False
        self._offset_s = 0.0
        self._start_mono = 0.0
        return self._track

    def play(self, start_s: float | None = None) -> None:
        if not self._track:
            return

        if start_s is None:
            start_s = self._offset_s
        start_s = max(0.0, float(start_s))

        try:
            pygame.mixer.music.play(loops=0, start=start_s)
            self._offset_s = start_s
        except TypeError:
            pygame.mixer.music.play(loops=0)
            self._offset_s = 0.0

        self._start_mono = time.monotonic()
        self._is_playing = True
        self._is_paused = False

    def pause(self) -> None:
        if not self._is_playing or self._is_paused:
            return
        pygame.mixer.music.pause()
        self._offset_s = self.get_pos_s()
        self._is_paused = True

    def unpause(self) -> None:
        if not self._is_playing or not self._is_paused:
            return
        pygame.mixer.music.unpause()
        self._start_mono = time.monotonic()
        self._is_paused = False

    def stop(self) -> None:
        pygame.mixer.music.stop()
        self._is_playing = False
        self._is_paused = False
        self._offset_s = 0.0
        self._start_mono = 0.0

    def seek(self, pos_s: float) -> None:
        if not self._track:
            return

        pos_s = float(pos_s)
        pos_s = max(0.0, min(pos_s, self._track.duration_s if self._track.duration_s else pos_s))

        self._offset_s = pos_s

        if self._is_playing:
            was_paused = self._is_paused
            self.play(start_s=pos_s)
            if was_paused:
                self.pause()

    def set_volume(self, v: float) -> None:
        pygame.mixer.music.set_volume(max(0.0, min(1.0, float(v))))

    def is_busy(self) -> bool:
        return bool(pygame.mixer.music.get_busy())

    def get_track(self) -> TrackInfo | None:
        return self._track

    def is_playing(self) -> bool:
        return self._is_playing

    def is_paused(self) -> bool:
        return self._is_paused

    def get_pos_s(self) -> float:
        if not self._is_playing:
            return self._offset_s
        if self._is_paused:
            return self._offset_s
        return self._offset_s + (time.monotonic() - self._start_mono)

    def shutdown(self) -> None:
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass

    @staticmethod
    def _get_duration(path: str) -> float:
        try:
            audio = MutagenFile(path)
            if audio is None or not hasattr(audio, "info") or audio.info is None:
                return 0.0
            length = getattr(audio.info, "length", 0.0) or 0.0
            return float(length)
        except Exception:
            return 0.0
    
    def get_cover_bytes(self) -> bytes | None:
        """
        Tries to extract embedded cover art from common audio formats.
        Returns raw image bytes (jpeg/png) or None if not found.
        """
        if not self._track:
            return None

        try:
            audio = MutagenFile(self._track.path)

            if audio is None:
                return None

            if hasattr(audio, "tags") and audio.tags is not None:
                for k in audio.tags.keys():
                    if str(k).startswith("APIC"):
                        apic = audio.tags[k]
                        return getattr(apic, "data", None)

            if hasattr(audio, "get"):
                covr = audio.get("covr")
                if covr:
                    return bytes(covr[0])

            if hasattr(audio, "pictures") and audio.pictures:
                return bytes(audio.pictures[0].data)

            return None

        except Exception:
            return None
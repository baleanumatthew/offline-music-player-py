import os
from dataclasses import dataclass
from typing import Any

from core.rt_audio_engine import RealTimeAudioEngine, TrackInfo
from mutagen._file import File as MutagenFile


@dataclass
class UIState:
    title: str = "No file loaded"
    artist: str = ""
    album: str = ""
    duration_s: float = 0.0
    pos_s: float = 0.0
    is_loaded: bool = False
    is_playing: bool = False
    is_paused: bool = False

    cover_bytes: bytes | None = None

    tempo: float = 1.0
    semitones: float = 0.0
    volume: float = 0.3

    is_applying_fx: bool = False
    fx_message: str = ""


class PlayerController:
    def __init__(self, engine: RealTimeAudioEngine):
        self.engine = engine
        self.state = UIState()
        self._path: str | None = None

        self.engine.set_volume(self.state.volume)

    def load(self, path: str) -> None:
        track: TrackInfo = self.engine.load(path)
        self._path = path
        meta_title, artist, album = _extract_metadata(path)

        self.state.title = meta_title or os.path.basename(track.path)
        self.state.artist = artist
        self.state.album = album
        self.state.duration_s = track.duration_s
        self.state.pos_s = 0.0
        self.state.is_loaded = True
        self.state.is_playing = False
        self.state.is_paused = False

        self.state.tempo = 1.0
        self.state.semitones = 0.0
        self.engine.set_tempo(1.0)
        self.engine.set_pitch_semitones(0.0)

        self.state.cover_bytes = _extract_cover_bytes(path)

        self.state.is_applying_fx = False
        self._update_fx_message()
        self.engine.set_volume(self.state.volume)

    def play(self) -> None:
        if not self.state.is_loaded:
            return

        if self.engine.is_playing() and self.engine.is_paused():
            self.engine.unpause()
        else:
            if self._is_at_end():
                self.state.pos_s = 0.0
            self.engine.seek(self.state.pos_s)
            self.engine.play()

        self._sync()

    def toggle_play_pause(self) -> None:
        if not self.state.is_loaded:
            return

        if self.engine.is_playing() and not self.engine.is_paused():
            self.engine.pause()
        else:
            self.play()

        self._sync()

    def pause_toggle(self) -> None:
        if not self.state.is_loaded:
            return
        if not self.engine.is_playing():
            return

        if self.engine.is_paused():
            self.engine.unpause()
        else:
            self.engine.pause()

        self._sync()

    def stop(self) -> None:
        if not self.state.is_loaded:
            return

        self.engine.stop()
        self.state.pos_s = 0.0
        self._sync()

    def seek(self, pos_s: float) -> None:
        if not self.state.is_loaded:
            return

        pos_s = float(pos_s)
        if self.state.duration_s > 0:
            pos_s = max(0.0, min(pos_s, self.state.duration_s))
        else:
            pos_s = max(0.0, pos_s)

        self.engine.seek(pos_s)
        self.state.pos_s = pos_s
        self._sync()

    def skip(self, delta_s: float) -> None:
        if not self.state.is_loaded:
            return
        self.seek(self.state.pos_s + float(delta_s))

    def set_tempo(self, tempo: float) -> None:
        tempo = float(max(0.5, min(2.0, tempo)))
        self.state.tempo = tempo
        self.engine.set_tempo(tempo)
        self._update_fx_message()

    def set_semitones(self, semitones: float) -> None:
        semitones = float(max(-12.0, min(12.0, semitones)))
        self.state.semitones = semitones
        self.engine.set_pitch_semitones(semitones)
        self._update_fx_message()

    def reset_fx(self) -> None:
        self.state.tempo = 1.0
        self.state.semitones = 0.0
        self.engine.set_tempo(1.0)
        self.engine.set_pitch_semitones(0.0)
        self._update_fx_message()

    def reset_tempo(self) -> None:
        self.state.tempo = 1.0
        self.engine.set_tempo(1.0)
        self._update_fx_message()

    def reset_pitch(self) -> None:
        self.state.semitones = 0.0
        self.engine.set_pitch_semitones(0.0)
        self._update_fx_message()

    def set_volume(self, v: float) -> None:
        v = float(v)
        if v < 0.0:
            v = 0.0
        elif v > 1.0:
            v = 1.0
        self.state.volume = v
        self.engine.set_volume(v)

    def tick(self) -> None:
        if not self.state.is_loaded:
            return

        pos = self.engine.get_pos_s()
        dur = self.state.duration_s
        if dur > 0:
            pos = max(0.0, min(pos, dur))
        self.state.pos_s = pos

        self._sync()

    def shutdown(self) -> None:
        self.engine.shutdown()

    def _sync(self) -> None:
        self.state.is_playing = self.engine.is_playing()
        self.state.is_paused = self.engine.is_paused()

    def _update_fx_message(self) -> None:
        sign = "+" if self.state.semitones >= 0 else ""
        self.state.fx_message = f"Tempo {self.state.tempo:.2f}x | Pitch {sign}{self.state.semitones:.0f} st"

    def _is_at_end(self) -> bool:
        if self.state.duration_s <= 0:
            return False
        return self.state.pos_s >= (self.state.duration_s - 0.05)


def _extract_metadata(path: str) -> tuple[str | None, str, str]:
    title: str | None = None
    artist = ""
    album = ""

    try:
        audio_easy = MutagenFile(path, easy=True)
        tags = getattr(audio_easy, "tags", None)
        if tags:
            title = _first_text(tags.get("title"))
            artist = (
                _first_text(tags.get("artist"))
                or _first_text(tags.get("albumartist"))
                or ""
            )
            album = _first_text(tags.get("album")) or ""
    except Exception:
        pass

    if title and artist and album:
        return title, artist, album

    try:
        audio_full = MutagenFile(path)
        tags = getattr(audio_full, "tags", None)
        if tags:
            if not title:
                title = _pick_tag_text(tags, ("TIT2", "\xa9nam", "title"))
            if not artist:
                artist = _pick_tag_text(tags, ("TPE1", "\xa9ART", "aART", "artist")) or ""
            if not album:
                album = _pick_tag_text(tags, ("TALB", "\xa9alb", "album")) or ""
    except Exception:
        pass

    return title, artist, album


def _pick_tag_text(tags: Any, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        try:
            value = tags.get(key)
        except Exception:
            value = None
        text = _first_text(value)
        if text:
            return text
    return None


def _first_text(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, (list, tuple)):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return None

    if hasattr(value, "text"):
        return _first_text(getattr(value, "text"))

    if isinstance(value, (bytes, bytearray)):
        try:
            text = bytes(value).decode("utf-8", errors="ignore").strip()
        except Exception:
            return None
        return text or None

    text = str(value).strip()
    return text or None


def _extract_cover_bytes(path: str) -> bytes | None:
    try:
        audio = MutagenFile(path)
        if audio is None:
            return None

        if audio.tags:
            for key in audio.tags.keys():
                if key.startswith("APIC"):
                    return audio.tags[key].data

        if hasattr(audio, "tags") and audio.tags:
            covr = audio.tags.get("covr")
            if covr:
                return bytes(covr[0])

        if hasattr(audio, "pictures") and audio.pictures:
            return audio.pictures[0].data

        return None
    except Exception:
        return None

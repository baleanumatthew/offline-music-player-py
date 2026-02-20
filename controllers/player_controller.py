import os
from dataclasses import dataclass
from core.rt_audio_engine import RealTimeAudioEngine, TrackInfo
from mutagen._file import File as MutagenFile

@dataclass
class UIState:
    title: str = "No file loaded"
    duration_s: float = 0.0
    pos_s: float = 0.0
    is_loaded: bool = False
    is_playing: bool = False
    is_paused: bool = False

    cover_bytes: bytes | None = None

    tempo: float = 1.0
    semitones: float = 0.0

    is_applying_fx: bool = False
    fx_message: str = ""

class PlayerController:
    def __init__(self, engine: RealTimeAudioEngine):
        self.engine = engine
        self.state = UIState()
        self._path: str | None = None

        self._volume = 1.0

    def load(self, path: str) -> None:
        track: TrackInfo = self.engine.load(path)
        self._path = path

        self.state.title = os.path.basename(track.path)
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
        self.state.fx_message = ""

    def play(self) -> None:
        if not self.state.is_loaded:
            return

        if self.engine.is_playing() and self.engine.is_paused():
            self.engine.unpause()
        else:
            self.engine.seek(self.state.pos_s)
            self.engine.play()

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

    def set_tempo(self, tempo: float) -> None:
        tempo = float(max(0.5, min(2.0, tempo)))
        self.state.tempo = tempo
        self.engine.set_tempo(tempo)

    def set_semitones(self, semitones: float) -> None:
        semitones = float(max(-12.0, min(12.0, semitones)))
        self.state.semitones = semitones
        self.engine.set_pitch_semitones(semitones)

    def set_volume(self, v: float) -> None:
        v = float(v)
        if v < 0.0:
            v = 0.0
        elif v > 1.0:
            v = 1.0
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
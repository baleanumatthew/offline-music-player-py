import os
import threading
from dataclasses import dataclass
import time
from core.audio_engine import AudioEngine, TrackInfo
from core.audio_processor import AudioProcessor, Effects


@dataclass
class UIState:
    title: str = "No file loaded"
    duration_s: float = 0.0
    pos_s: float = 0.0
    is_loaded: bool = False
    is_playing: bool = False
    is_paused: bool = False
    cover_bytes: bytes | None = None
    is_previewing: bool = False

    tempo: float = 1.0
    semitones: float = 0.0
    is_applying_fx: bool = False
    fx_message: str = ""

class PlayerController:
    def __init__(self, engine: AudioEngine):
        self.engine = engine
        self.processor = AudioProcessor()
        self.state = UIState()

        self._fx_job_lock = threading.Lock()
        self._fx_job_id = 0

        self._source_path: str | None = None
        self._current_play_path: str | None = None
        self._preview_origin_src_s = 0.0
        self._fx_request_src_s = 0.0
        self._fx_request_time = 0.0
        self._apply_debounce_timer = None

    def load(self, path: str) -> None:
        self.processor.load_source(path)
        self._source_path = path
        self._current_play_path = path
        
        track: TrackInfo = self.engine.load(path)

        self.state.title = os.path.basename(track.path)
        self.state.duration_s = track.duration_s
        self.state.pos_s = 0.0
        self.state.is_loaded = True
        self.state.is_playing = False
        self.state.is_paused = False
        self.state.cover_bytes = self.engine.get_cover_bytes()

        self.state.tempo = 1.0
        self.state.semitones = 0.0
        self.state.is_applying_fx = False
        self.state.fx_message = ""

    def play(self) -> None:
        if not self.state.is_loaded:
            return

        if self.engine.is_playing() and self.engine.is_paused():
            self.engine.unpause()
        else:
            self.engine.play(start_s=self.state.pos_s)

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
        self.engine.seek(pos_s)
        self.state.pos_s = float(pos_s)
        self._sync()

    def set_volume(self, v: float) -> None:
        self.engine.set_volume(v)

    def tick(self) -> None:
        if not self.state.is_loaded:
            return

        pos = self.engine.get_pos_s()
        dur = self.state.duration_s
        if dur > 0:
            pos = max(0.0, min(pos, dur))
        self.state.pos_s = pos

        if self.engine.is_playing() and (not self.engine.is_busy()) and (not self.engine.is_paused()):
            self.engine.stop()
            self.state.pos_s = 0.0

        self._sync()

    def shutdown(self) -> None:
        self.engine.shutdown()

    def _sync(self) -> None:
        self.state.is_playing = self.engine.is_playing()
        self.state.is_paused = self.engine.is_paused()

    def set_tempo(self, tempo: float) -> None:
        self.state.tempo = float(max(0.5, min(2.0, tempo)))

    def set_semitones(self, semitones: float) -> None:
        self.state.semitones = float(max(-12.0, min(12.0, semitones)))

    def apply_fx_async(self) -> None:
        if not self.state.is_loaded or not self._source_path:
            return

        effects = Effects(tempo=self.state.tempo, semitones=self.state.semitones)

        if abs(effects.tempo - 1.0) < 1e-6 and abs(effects.semitones) < 1e-6:
            self._reload_playback_path(self._source_path, self.state.pos_s, autoplay=True)
            self.state.is_applying_fx = False
            self.state.fx_message = ""
            self.state.is_previewing = False
            return

        src_pos = float(self.state.pos_s)
        t0 = time.monotonic()

        with self._fx_job_lock:
            self._fx_job_id += 1
            job_id = self._fx_job_id

        self._fx_request_src_s = src_pos
        self._fx_request_time = t0

        self.state.is_applying_fx = True
        self.state.fx_message = "Applying effects…"
        self.state.is_previewing = False

        self.engine.stop()

        def preview_worker():
            try:
                preview_path = self.processor.render_preview(effects, start_s=src_pos, length_s=10.0)
            except Exception as e:
                preview_path = None
                err = str(e)

            with self._fx_job_lock:
                if job_id != self._fx_job_id:
                    return

            if preview_path is None:
                self.state.is_applying_fx = False
                self.state.fx_message = f"Preview FX failed: {err}"
                return

            self._preview_origin_src_s = src_pos
            self._reload_playback_path(preview_path, resume_pos=0.0, autoplay=True)
            self.state.is_previewing = True
            self.state.fx_message = "Applying effects… (rendering full track)"

        def full_worker():
            try:
                full_path = self.processor.render(effects)
            except Exception as e:
                full_path = None
                err = str(e)

            with self._fx_job_lock:
                if job_id != self._fx_job_id:
                    return

            if full_path is None:
                self.state.is_applying_fx = False
                self.state.fx_message = f"Full FX failed: {err}"
                return

            dt = time.monotonic() - t0
            src_now = src_pos + dt
            proc_now = src_now / effects.tempo

            self._reload_playback_path(full_path, resume_pos=proc_now, autoplay=True)
            self.state.is_previewing = False
            self.state.is_applying_fx = False
            self.state.fx_message = ""

        threading.Thread(target=preview_worker, daemon=True).start()
        threading.Thread(target=full_worker, daemon=True).start()

    def _reload_playback_path(self, path: str, resume_pos: float, autoplay: bool) -> None:
        """
        Stop current playback, load new file, and resume at approx position.
        Note: tempo changes change track length; we keep a best-effort same time offset.
        """
        self.engine.stop()
        self.engine.load(path)
        self._current_play_path = path

        tr = self.engine.get_track()
        if tr:
            self.state.duration_s = tr.duration_s

        if self.state.duration_s > 0:
            resume_pos = max(0.0, min(resume_pos, self.state.duration_s))
        else:
            resume_pos = max(0.0, resume_pos)

        self.state.pos_s = resume_pos

        if autoplay:
            self.engine.play(start_s=resume_pos)
    
    def apply_fx_debounced(self, delay_ms: int = 180) -> None:
        """
        Debounce FX application: if called repeatedly, only apply once after user pauses.
        UI calls this after every button/keypress adjustment.
        """
        self.apply_fx_async()
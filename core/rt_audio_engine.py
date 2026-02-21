import subprocess
import threading
import traceback
from dataclasses import dataclass
from typing import Optional
from collections import deque
import numpy as np
import sounddevice as sd
import soundfile as sf
import pylibrb
from pylibrb import RubberBandStretcher, Option
import sys
import os


@dataclass
class TrackInfo:
    path: str
    duration_s: float
    sample_rate: int
    channels: int


def _load_any_audio_ffmpeg(
    path: str,
    target_sr: int = 48000,
    target_channels: int = 2,
) -> tuple[np.ndarray, int]:

    try:
        data, sr = sf.read(path, always_2d=True, dtype="float32")

        if int(sr) != int(target_sr):
            raise RuntimeError("Needs resample; fallback to ffmpeg")

        return np.ascontiguousarray(data, dtype=np.float32), int(sr)
    except Exception:
        pass

    cmd = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel", "error",
        "-i", path,
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ac", str(int(target_channels)),
        "-ar", str(int(target_sr)),
        "pipe:1",
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Install ffmpeg and ensure it is in PATH.")

    out, err = proc.communicate()
    if proc.returncode != 0:
        msg = err.decode(errors="replace").strip() if err else "ffmpeg decode failed"
        raise RuntimeError(f"ffmpeg failed: {msg}")

    audio = np.frombuffer(out, dtype=np.float32)
    if audio.size == 0:
        raise RuntimeError("ffmpeg produced no audio samples.")

    if audio.size % target_channels != 0:
        audio = audio[: audio.size - (audio.size % target_channels)]

    audio = audio.reshape((-1, target_channels))
    return np.ascontiguousarray(audio, dtype=np.float32), int(target_sr)


class RealTimeAudioEngine:
    def __init__(self, blocksize: int = 1024, target_sr: int = 48000, target_channels: int = 2):
        self.blocksize = int(blocksize)
        self.target_sr = int(target_sr)
        self.target_channels = int(target_channels)

        self._lock = threading.RLock()

        self._track: Optional[TrackInfo] = None
        self._audio: Optional[np.ndarray] = None
        self._sr: int = self.target_sr
        self._ch: int = self.target_channels

        self._stream: Optional[sd.OutputStream] = None

        self._playing = False
        self._paused = False

        self._in_pos = 0

        self._stretcher: Optional[RubberBandStretcher] = None

        self._tempo = 1.0
        self._pitch_semitones = 0.0
        self._volume = 1.0

        self._outq: deque[np.ndarray] = deque()
        self._outq_frames: int = 0


    def load(self, path: str) -> TrackInfo:
        audio, sr = _load_any_audio_ffmpeg(path, target_sr=self.target_sr, target_channels=self.target_channels)

        with self._lock:
            self._audio = audio
            self._sr = int(sr)
            self._ch = int(audio.shape[1])

            self._in_pos = 0
            self._clear_outq_locked()

            dur_s = float(len(audio) / self._sr) if self._sr > 0 else 0.0
            self._track = TrackInfo(path=path, duration_s=dur_s, sample_rate=self._sr, channels=self._ch)

            self._playing = False
            self._paused = False

            self._build_stretcher_locked()

        return self._track

    def play(self) -> None:
        with self._lock:
            if self._audio is None:
                return
            if self._stream is None:
                self._open_stream_locked()
            self._playing = True
            self._paused = False

    def pause(self) -> None:
        with self._lock:
            if self._playing:
                self._paused = True

    def unpause(self) -> None:
        with self._lock:
            if self._playing:
                self._paused = False

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._paused = False
            self._in_pos = 0
            self._clear_outq_locked()
            self._build_stretcher_locked()

    def seek(self, pos_s: float) -> None:
        with self._lock:
            if self._audio is None:
                return
            pos_s = float(max(0.0, pos_s))
            new_in_pos = int(pos_s * self._sr)
            new_in_pos = max(0, min(new_in_pos, len(self._audio)))

            self._in_pos = new_in_pos
            self._clear_outq_locked()
            self._build_stretcher_locked()

    def set_pitch_semitones(self, semitones: float) -> None:
        with self._lock:
            self._pitch_semitones = float(semitones)
            if self._stretcher is not None:
                self._stretcher.pitch_scale = 2.0 ** (self._pitch_semitones / 12.0)

    def set_tempo(self, tempo: float) -> None:
        with self._lock:
            self._tempo = float(max(0.25, min(4.0, tempo)))
            if self._stretcher is not None:
                self._stretcher.time_ratio = 1.0 / max(1e-6, self._tempo)

    def set_volume(self, v: float) -> None:
        with self._lock:
            self._volume = float(max(0.0, min(1.0, v)))

    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def is_loaded(self) -> bool:
        with self._lock:
            return self._audio is not None

    def get_track(self) -> Optional[TrackInfo]:
        with self._lock:
            return self._track

    def get_pos_s(self) -> float:
        with self._lock:
            if self._sr <= 0:
                return 0.0
            return float(self._in_pos) / float(self._sr)

    def shutdown(self) -> None:
        with self._lock:
            self._playing = False
            self._paused = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                except Exception:
                    pass
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None


    def _log_rt_error(self, msg: str) -> None:
        try:
            with open("rt_audio_errors.log", "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _clear_outq_locked(self) -> None:
        self._outq.clear()
        self._outq_frames = 0

    def _open_stream_locked(self) -> None:
        self._stream = sd.OutputStream(
            samplerate=self._sr,
            channels=self._ch,
            blocksize=self.blocksize,
            dtype="float32",
            latency="high",
            callback=self._callback,
        )
        self._stream.start()

    def _build_stretcher_locked(self) -> None:
        opts = (
            Option.PROCESS_REALTIME
            | Option.ENGINE_FINER
            | Option.CHANNELS_TOGETHER
            | Option.PHASE_LAMINAR
            | Option.SMOOTHING_ON
            | Option.WINDOW_STANDARD
            | Option.TRANSIENTS_MIXED
            | Option.THREADING_AUTO
        )
        time_ratio = 1.0 / max(1e-6, self._tempo)

        st = RubberBandStretcher(
            sample_rate=self._sr,
            channels=self._ch,
            options=opts,
            initial_time_ratio=time_ratio
            )

        if hasattr(st, "set_max_process_size"):
            try:
                st.set_max_process_size(self.blocksize)
                st.formant_scale = pylibrb.AUTO_FORMANT_SCALE
            except Exception:
                pass

        try:
            st.time_ratio = time_ratio
        except Exception:
            pass

        try:
            st.pitch_scale = 2.0 ** (self._pitch_semitones / 12.0)
        except Exception:
            pass

        self._stretcher = st

    def _get_available_frames_locked(self) -> int:
        st = self._stretcher
        if st is None:
            return 0
        for name in ("available", "available_samples", "get_available", "get_samples_available"):
            if hasattr(st, name):
                try:
                    return int(getattr(st, name)())
                except Exception:
                    return 0
        return 0

    def _retrieve_locked(self, n: int) -> Optional[np.ndarray]:
        st = self._stretcher
        if st is None:
            return None

        candidates = (
            ("retrieve", (n,)),
            ("retrieve_samples", (n,)),
            ("retrieve_available", tuple()),
            ("retrieve_available_samples", tuple()),
        )

        for name, args in candidates:
            if hasattr(st, name):
                try:
                    return getattr(st, name)(*args)
                except Exception:
                    return None
        return None

    def _from_rb_locked(self, rb_out: np.ndarray) -> np.ndarray:
        arr = np.asarray(rb_out)
        if arr.ndim == 2 and arr.shape[0] == self._ch:
            arr = arr.T
        elif arr.ndim == 1:
            arr = arr.reshape((-1, 1))
        return np.ascontiguousarray(arr, dtype=np.float32)

    def _append_out_locked(self, out: np.ndarray) -> None:
        if out is None or out.size == 0:
            return
        out = np.ascontiguousarray(out, dtype=np.float32)
        self._outq.append(out)
        self._outq_frames += int(out.shape[0])

    def _ensure_outq_locked(self, frames_needed: int) -> None:
        if self._audio is None or self._stretcher is None:
            return

        target = frames_needed + (self.blocksize * 2)
        safety_iters = 0

        while self._outq_frames < target and safety_iters < 24:
            safety_iters += 1

            remaining = len(self._audio) - self._in_pos
            in_n = min(self.blocksize, remaining)

            if in_n <= 0:
                avail = self._get_available_frames_locked()
                if avail > 0:
                    rb_out = self._retrieve_locked(avail)
                    if rb_out is not None:
                        out = self._from_rb_locked(rb_out)
                        self._append_out_locked(out)
                    continue
                self._playing = False
                self._paused = False
                return

            in_chunk = self._audio[self._in_pos:self._in_pos + in_n]
            self._in_pos += in_n
            in_chunk = np.ascontiguousarray(in_chunk, dtype=np.float32)

            rb_in = pylibrb.create_audio_array(int(self._ch), int(in_n))
            rb_in[:, :] = in_chunk.T

            self._stretcher.process(rb_in)

            avail = self._get_available_frames_locked()
            if avail > 0:
                rb_out = self._retrieve_locked(avail)
                if rb_out is not None:
                    out = self._from_rb_locked(rb_out)
                    self._append_out_locked(out)

    def _callback(self, outdata, frames, time_info, status):
        try:
            with self._lock:
                if (not self._playing) or self._paused or self._audio is None or self._stretcher is None:
                    outdata[:] = 0
                    return

                self._ensure_outq_locked(frames)

                outdata[:] = 0
                need = frames
                written = 0

                while need > 0 and self._outq_frames > 0:
                    chunk = self._outq[0]
                    take = min(need, int(chunk.shape[0]))

                    outdata[written:written + take] = chunk[:take] * self._volume

                    if take == chunk.shape[0]:
                        self._outq.popleft()
                    else:
                        self._outq[0] = chunk[take:]

                    self._outq_frames -= take
                    written += take
                    need -= take

        except Exception:
            outdata[:] = 0
            self._log_rt_error(traceback.format_exc())

def _ffmpeg_exe() -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        bundled = os.path.join(base, "ffmpeg.exe")
        if os.path.exists(bundled):
            return bundled
        bundled2 = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
        if os.path.exists(bundled2):
            return bundled2
        return "ffmpeg"

    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ffmpeg.exe")
    if os.path.exists(local):
        return local
    return "ffmpeg"
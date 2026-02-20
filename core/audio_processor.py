import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from pydub import AudioSegment

@dataclass(frozen=True)
class Effects:
    tempo: float
    semitones: float

class AudioProcessor:
    """
    Full-track processing via Rubber Band CLI (single pass).
    - Robust input formats via ffmpeg (pydub)
    - One call: tempo + pitch together => fewer artifacts + faster than two-pass
    - Uses R3 engine + formant preservation + centre focus by default
    - Caches outputs
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._src_path: str | None = None
        self._cache: dict[Effects, str] = {}
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="tk_music_rb_"))
        self._decoded_wav: Path | None = None

        self._rb_base_flags = ["-3", "-F", "--centre-focus", "-q"]

    def load_source(self, path: str) -> None:
        """
        Decode source to a stable WAV for Rubber Band.
        This avoids format variability and speeds up repeated renders.
        """
        with self._lock:
            self._src_path = path
            self._cache.clear()

        seg = AudioSegment.from_file(path) 
        seg = seg.set_sample_width(2)       

        wav_path = self._tmp_dir / "decoded_source.wav"
        seg.export(wav_path, format="wav")

        with self._lock:
            self._decoded_wav = wav_path

    def render(self, effects: Effects) -> str:
        effects = Effects(
            tempo=float(max(0.25, min(4.0, effects.tempo))),
            semitones=float(max(-24.0, min(24.0, effects.semitones))),
        )

        with self._lock:
            if effects in self._cache:
                return self._cache[effects]
            if self._decoded_wav is None:
                raise RuntimeError("AudioProcessor: no source loaded/decoded.")
            in_wav = self._decoded_wav

        out_wav = self._tmp_dir / f"rb_t{effects.tempo:.3f}_p{effects.semitones:.3f}.wav"

        cmd = ["rubberband", *self._rb_base_flags, f"-T{effects.tempo}", f"-p{effects.semitones}", str(in_wav), str(out_wav)]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode(errors="replace") if e.stderr else "rubberband failed"
            raise RuntimeError(err)

        with self._lock:
            self._cache[effects] = str(out_wav)

        return str(out_wav)
    
    def render_preview(self, effects: Effects, start_s: float, length_s: float = 10.0) -> str:
        effects = Effects(
            tempo=float(max(0.25, min(4.0, effects.tempo))),
            semitones=float(max(-24.0, min(24.0, effects.semitones))),
        )

        with self._lock:
            if self._src_path is None:
                raise RuntimeError("AudioProcessor: no source loaded.")
            src_path = self._src_path

        seg = AudioSegment.from_file(src_path)
        start_ms = int(max(0.0, start_s) * 1000)
        end_ms = int((max(0.0, start_s) + max(1.0, length_s)) * 1000)
        clip = seg[start_ms:end_ms].set_sample_width(2)

        in_clip = self._tmp_dir / "preview_in.wav"
        out_clip = self._tmp_dir / f"preview_out_t{effects.tempo:.3f}_p{effects.semitones:.3f}.wav"
        clip.export(in_clip, format="wav")

        cmd = ["rubberband", "-2", "-q", f"-T{effects.tempo}", f"-p{effects.semitones}", str(in_clip), str(out_clip)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        return str(out_clip)
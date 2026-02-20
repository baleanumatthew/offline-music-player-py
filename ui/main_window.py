import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk


class MainWindow(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.title("Music Player")
        self.geometry("540x420")
        self.resizable(True, True)

        self._ignore_scale = False
        self._scrubbing = False

        self._tempo_step = 0.02
        self._pitch_step = 1.0

        self._tempo_min = 0.5
        self._tempo_max = 2.0
        self._pitch_min = -12.0
        self._pitch_max = 12.0

        self._cover_imgtk = None

        self._apply_fx_after_id = None



        self._build_ui()
        self._apply_enabled(False)

        self.bind("<Left>", lambda e: self._nudge_tempo(-1))
        self.bind("<Right>", lambda e: self._nudge_tempo(+1))
        self.bind("<Down>", lambda e: self._nudge_pitch(-1))
        self.bind("<Up>", lambda e: self._nudge_pitch(+1))

        self.focus_set()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        row1 = ttk.Frame(root)
        row1.pack(fill="x")

        self.lbl_file = ttk.Label(row1, text="No file loaded", width=52)
        self.lbl_file.pack(side="left", padx=(0, 8))

        ttk.Button(row1, text="Open…", command=self._open).pack(side="right")

        cover_frame = ttk.Frame(root)
        cover_frame.pack(fill="x", pady=(12, 0))

        self.cover_label = ttk.Label(cover_frame, text="(No cover art)")
        self.cover_label.pack(anchor="center")

        self.status_label = ttk.Label(root, text="", foreground="")
        self.status_label.pack(fill="x", pady=(8, 0))

        row2 = ttk.Frame(root)
        row2.pack(fill="x", pady=(16, 6))

        self.lbl_left = ttk.Label(row2, text="00:00")
        self.lbl_left.pack(side="left")

        self.scale = ttk.Scale(row2, from_=0, to=100, orient="horizontal", command=self._on_scale_move)
        self.scale.pack(side="left", fill="x", expand=True, padx=10)

        self.lbl_right = ttk.Label(row2, text="00:00")
        self.lbl_right.pack(side="right")

        self.scale.bind("<ButtonPress-1>", self._on_scrub_start)
        self.scale.bind("<ButtonRelease-1>", self._on_scrub_end)

        row3 = ttk.Frame(root)
        row3.pack(pady=(10, 0))

        self.btn_play = ttk.Button(row3, text="Play", command=self._play)
        self.btn_pause = ttk.Button(row3, text="Pause", command=self._pause)
        self.btn_stop = ttk.Button(row3, text="Stop", command=self._stop)

        self.btn_play.grid(row=0, column=0, padx=6)
        self.btn_pause.grid(row=0, column=1, padx=6)
        self.btn_stop.grid(row=0, column=2, padx=6)

        row4 = ttk.Frame(root)
        row4.pack(fill="x", pady=(18, 0))

        ttk.Label(row4, text="Volume").pack(side="left")
        self.vol = ttk.Scale(row4, from_=0, to=1, value=0.3, orient="horizontal", command=self._on_volume)
        self.vol.pack(side="left", fill="x", expand=True, padx=10)
        self.controller.set_volume(0.3)

        fx_frame = ttk.LabelFrame(root, text="Effects")
        fx_frame.pack(fill="x", pady=(14, 0))

        tempo_row = ttk.Frame(fx_frame)
        tempo_row.pack(fill="x", pady=(6, 2), padx=8)

        ttk.Label(tempo_row, text="Tempo").pack(side="left")



        self.btn_tempo_down = ttk.Button(tempo_row, text="◀", width=4, command=lambda: self._nudge_tempo(-1))
        self.tempo_display = ttk.Label(tempo_row, text="1.00×", width=8)
        self.tempo_display.pack(side="right")
        self.btn_tempo_up = ttk.Button(tempo_row, text="▶", width=4, command=lambda: self._nudge_tempo(+1))
        self.btn_tempo_down.pack(side="right", padx=(0, 6))
        self.btn_tempo_up.pack(side="right")

        pitch_row = ttk.Frame(fx_frame)
        pitch_row.pack(fill="x", pady=(2, 6), padx=8)

        ttk.Label(pitch_row, text="Pitch").pack(side="left")

        self.btn_pitch_down = ttk.Button(pitch_row, text="◀", width=4, command=lambda: self._nudge_pitch(-1))
        self.pitch_display = ttk.Label(pitch_row, text="+0 st", width=8)
        self.pitch_display.pack(side="right")
        self.btn_pitch_up = ttk.Button(pitch_row, text="▶", width=4, command=lambda: self._nudge_pitch(+1))
        self.btn_pitch_down.pack(side="right", padx=(0, 6))
        self.btn_pitch_up.pack(side="right")

    def _apply_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_play.configure(state=state)
        self.btn_pause.configure(state=state)
        self.btn_stop.configure(state=state)
        self.scale.state(["!disabled"] if enabled else ["disabled"])
        self.vol.state(["!disabled"] if enabled else ["disabled"])
        self.btn_tempo_down.configure(state=state)
        self.btn_tempo_up.configure(state=state)
        self.btn_pitch_down.configure(state=state)
        self.btn_pitch_up.configure(state=state)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def _set_cover_art(self, cover_bytes: bytes | None):
        if not cover_bytes:
            self.cover_label.configure(image="", text="(No cover art)")
            self._cover_imgtk = None
            return

        try:
            img = Image.open(io.BytesIO(cover_bytes))
            img.thumbnail((140, 140))
            imgtk = ImageTk.PhotoImage(img)

            self.cover_label.configure(image=imgtk, text="")
            self._cover_imgtk = imgtk
        except Exception:
            self.cover_label.configure(image="", text="(Cover art unreadable)")
            self._cover_imgtk = None

    def _open(self):
        path = filedialog.askopenfilename(
            title="Choose an audio file",
            filetypes=[
                ("Audio", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            self.controller.load(path)
        except Exception as e:
            messagebox.showerror("Load failed", str(e))
            return

        st = self.controller.state
        self.lbl_file.configure(text=st.title)
        self.lbl_right.configure(text=self._fmt_time(st.duration_s))
        self.lbl_left.configure(text="00:00")
        self._set_cover_art(st.cover_bytes)

        self.tempo_display.configure(text="1.00×")
        self.pitch_display.configure(text="+0 st")

        self._ignore_scale = True
        self.scale.configure(from_=0, to=max(st.duration_s, 1.0))
        self.scale.set(0)
        self._ignore_scale = False

        self._apply_enabled(True)

    def _play(self):
        self.controller.play()

    def _pause(self):
        self.controller.pause_toggle()

    def _stop(self):
        self.controller.stop()

    def _on_volume(self, _):
        self.controller.set_volume(float(self.vol.get()))

    def _on_scrub_start(self, _evt):
        if not self.controller.state.is_loaded:
            return
        self._scrubbing = True

    def _on_scale_move(self, _value):
        if self._ignore_scale:
            return
        if self._scrubbing:
            self.lbl_left.configure(text=self._fmt_time(float(self.scale.get())))

    def _on_scrub_end(self, _evt):
        if not self.controller.state.is_loaded:
            return
        self._scrubbing = False
        self.controller.seek(float(self.scale.get()))

    def _on_fx_release(self, _evt):
        if not self.controller.state.is_loaded:
            return
        self.controller.apply_fx_async()

    def _tick_ui(self):
        self.controller.tick()
        st = self.controller.state

        self.status_label.configure(text=st.fx_message if st.is_applying_fx or st.fx_message else "")

        if st.is_loaded and not self._scrubbing:
            self.lbl_left.configure(text=self._fmt_time(st.pos_s))
            self.lbl_right.configure(text=self._fmt_time(st.duration_s))

            self._ignore_scale = True
            self.scale.configure(to=max(st.duration_s, 1.0))
            self.scale.set(st.pos_s)
            self._ignore_scale = False

        self.after(200, self._tick_ui)

    def _on_close(self):
        try:
            self.controller.shutdown()
        finally:
            self.destroy()
    
    def _schedule_apply_fx(self):
        """
        Debounce: if user presses keys quickly, only render once after they pause.
        """
        if not self.controller.state.is_loaded:
            return

        if self._apply_fx_after_id is not None:
            self.after_cancel(self._apply_fx_after_id)

        self._apply_fx_after_id = self.after(200, self._apply_fx_now)

    def _apply_fx_now(self):
        self._apply_fx_after_id = None
        self.controller.apply_fx_async()

    def _nudge_tempo(self, direction: int):
        if not self.controller.state.is_loaded:
            return

        st = self.controller.state
        new_t = st.tempo + (direction * self._tempo_step)
        new_t = max(self._tempo_min, min(self._tempo_max, new_t))

        self.controller.set_tempo(new_t)
        self.tempo_display.configure(text=f"{new_t:.2f}×")

        self._schedule_apply_fx()

    def _nudge_pitch(self, direction: int):
        if not self.controller.state.is_loaded:
            return

        st = self.controller.state
        new_p = st.semitones + (direction * self._pitch_step)
        new_p = max(self._pitch_min, min(self._pitch_max, new_p))

        self.controller.set_semitones(new_p)
        sign = "+" if new_p >= 0 else ""
        self.pitch_display.configure(text=f"{sign}{new_p:.0f} st")

        self._schedule_apply_fx()
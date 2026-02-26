import io
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk


class MainWindow(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.title("Offline Music Player")
        self.geometry("900x640")
        self.minsize(760, 560)

        self._ignore_scale = False
        self._scrubbing = False

        self._tempo_step = 0.02
        self._pitch_step = 1.0

        self._tempo_min = 0.5
        self._tempo_max = 2.0
        self._pitch_min = -12.0
        self._pitch_max = 12.0

        self._cover_imgtk = None
        self._volume_dragging = False
        self._shortcut_tag = "PlayerShortcuts"

        self._build_styles()
        self._build_ui()
        self._apply_enabled(False)
        self._bind_shortcuts()
        self.focus_set()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick_ui()

    def _build_styles(self):
        self._palette = {
            "app_bg": "#000000",
            "card_bg": "#0a0a0a",
            "cover_bg": "#141414",
            "text": "#f3f4f6",
            "muted": "#a3a3a3",
            "primary_btn": "#242424",
            "primary_btn_active": "#323232",
            "soft_btn": "#1c1c1c",
            "soft_btn_active": "#2a2a2a",
            "play_bg": "#1f1f1f",
            "play_fg": "#d7dbe2",
            "pause_bg": "#292929",
            "pause_fg": "#c6c9cf",
            "stop_bg": "#222222",
            "stop_fg": "#d1d5db",
            "value_bg": "#080808",
            "scale_trough": "#2b2b2b",
            "timeline_knob": "#6b7280",
            "timeline_knob_active": "#7d8696",
            "volume_knob": "#52525b",
            "volume_knob_active": "#656573",
            "scale_border": "#3a3a3a",
        }

        self.configure(bg=self._palette["app_bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self._palette["app_bg"])
        style.configure("Card.TFrame", background=self._palette["card_bg"])
        style.configure("Cover.TFrame", background=self._palette["cover_bg"])

        style.configure(
            "HeaderTitle.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["text"],
            font=("Segoe UI Semibold", 18),
        )
        style.configure(
            "HeaderSub.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["muted"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "SectionTitle.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["text"],
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "TrackTitle.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["text"],
            font=("Segoe UI Semibold", 22),
        )
        style.configure(
            "Meta.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["muted"],
            font=("Segoe UI", 11),
        )
        style.configure(
            "Muted.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["muted"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Mono.TLabel",
            background=self._palette["card_bg"],
            foreground=self._palette["text"],
            font=("Consolas", 11),
        )
        style.configure(
            "Cover.TLabel",
            background=self._palette["cover_bg"],
            foreground=self._palette["muted"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Value.TLabel",
            background=self._palette["value_bg"],
            foreground=self._palette["text"],
            padding=(10, 4),
            font=("Consolas", 11),
        )
        style.configure(
            "BadgeStop.TLabel",
            background=self._palette["stop_bg"],
            foreground=self._palette["stop_fg"],
            padding=(12, 3),
            font=("Segoe UI Semibold", 9),
        )
        style.configure(
            "BadgePlaying.TLabel",
            background=self._palette["play_bg"],
            foreground=self._palette["play_fg"],
            padding=(12, 3),
            font=("Segoe UI Semibold", 9),
        )
        style.configure(
            "BadgePaused.TLabel",
            background=self._palette["pause_bg"],
            foreground=self._palette["pause_fg"],
            padding=(12, 3),
            font=("Segoe UI Semibold", 9),
        )

        style.configure(
            "PrimaryMuted.TButton",
            background=self._palette["primary_btn"],
            foreground=self._palette["text"],
            borderwidth=0,
            focusthickness=0,
            padding=(16, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "PrimaryMuted.TButton",
            background=[
                ("pressed", self._palette["primary_btn_active"]),
                ("active", self._palette["primary_btn_active"]),
                ("disabled", "#161616"),
            ],
            foreground=[("disabled", "#676767")],
        )
        style.configure(
            "Soft.TButton",
            background=self._palette["soft_btn"],
            foreground=self._palette["text"],
            borderwidth=0,
            focusthickness=0,
            padding=(12, 8),
            font=("Segoe UI", 10),
        )
        style.map(
            "Soft.TButton",
            background=[
                ("pressed", self._palette["soft_btn_active"]),
                ("active", self._palette["soft_btn_active"]),
                ("disabled", "#101010"),
            ],
            foreground=[("disabled", "#666666")],
        )
        style.configure(
            "Timeline.Horizontal.TScale",
            background=self._palette["timeline_knob"],
            troughcolor=self._palette["scale_trough"],
            bordercolor=self._palette["scale_border"],
            lightcolor=self._palette["timeline_knob_active"],
            darkcolor=self._palette["scale_border"],
        )
        style.map(
            "Timeline.Horizontal.TScale",
            background=[
                ("active", self._palette["timeline_knob_active"]),
                ("disabled", "#2b2b2b"),
            ],
        )
        style.configure(
            "Volume.Horizontal.TScale",
            background=self._palette["volume_knob"],
            troughcolor=self._palette["scale_trough"],
            bordercolor=self._palette["scale_border"],
            lightcolor=self._palette["volume_knob_active"],
            darkcolor=self._palette["scale_border"],
        )
        style.map(
            "Volume.Horizontal.TScale",
            background=[
                ("active", self._palette["volume_knob_active"]),
                ("disabled", "#2b2b2b"),
            ],
        )

    def _build_ui(self):
        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)

        header = ttk.Frame(root, style="Card.TFrame", padding=(18, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Offline Music Player", style="HeaderTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.lbl_header_hint = ttk.Label(
            header,
            text="Load a track to start listening.",
            style="HeaderSub.TLabel",
        )
        self.lbl_header_hint.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.btn_open = ttk.Button(
            header, text="Open File", style="PrimaryMuted.TButton", command=self._open
        )
        self.btn_open.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        now_playing = ttk.Frame(root, style="Card.TFrame", padding=18)
        now_playing.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        now_playing.columnconfigure(1, weight=1)

        cover_shell = ttk.Frame(now_playing, style="Cover.TFrame", width=170, height=170)
        cover_shell.grid(row=0, column=0, rowspan=3, sticky="nsw", padx=(0, 18))
        cover_shell.grid_propagate(False)

        self.cover_label = ttk.Label(
            cover_shell,
            text="No cover art",
            style="Cover.TLabel",
            anchor="center",
            justify="center",
        )
        self.cover_label.place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_track_title = ttk.Label(
            now_playing, text="No file loaded", style="TrackTitle.TLabel"
        )
        self.lbl_track_title.grid(row=0, column=1, sticky="w")

        self.lbl_track_meta = ttk.Label(
            now_playing,
            text="Artist and album metadata appears here.",
            style="Meta.TLabel",
        )
        self.lbl_track_meta.grid(row=1, column=1, sticky="w", pady=(4, 0))

        status_row = ttk.Frame(now_playing, style="Card.TFrame")
        status_row.grid(row=2, column=1, sticky="ew", pady=(12, 0))
        status_row.columnconfigure(1, weight=1)

        self.lbl_playback_state = ttk.Label(
            status_row, text="Stopped", style="BadgeStop.TLabel"
        )
        self.lbl_playback_state.grid(row=0, column=0, sticky="w")

        self.status_label = ttk.Label(status_row, text="", style="Muted.TLabel")
        self.status_label.grid(row=0, column=1, sticky="e")

        timeline = ttk.Frame(root, style="Card.TFrame", padding=(18, 14))
        timeline.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        timeline.columnconfigure(1, weight=1)

        self.lbl_left = ttk.Label(timeline, text="00:00", style="Mono.TLabel")
        self.lbl_left.grid(row=0, column=0, sticky="w")

        self.scale = ttk.Scale(
            timeline,
            from_=0,
            to=100,
            orient="horizontal",
            command=self._on_scale_move,
            style="Timeline.Horizontal.TScale",
        )
        self.scale.grid(row=0, column=1, sticky="ew", padx=12)

        self.lbl_right = ttk.Label(timeline, text="00:00", style="Mono.TLabel")
        self.lbl_right.grid(row=0, column=2, sticky="e")

        self.lbl_remaining = ttk.Label(
            timeline, text="Remaining 00:00", style="Muted.TLabel"
        )
        self.lbl_remaining.grid(row=1, column=1, sticky="e", pady=(6, 0))

        self.scale.bind("<ButtonPress-1>", self._on_scrub_start)
        self.scale.bind("<ButtonRelease-1>", self._on_scrub_end)

        bottom = ttk.Frame(root, style="App.TFrame")
        bottom.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=2)

        controls = ttk.Frame(bottom, style="Card.TFrame", padding=18)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        controls.columnconfigure(0, weight=1)

        ttk.Label(controls, text="Playback", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        play_row = ttk.Frame(controls, style="Card.TFrame")
        play_row.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.btn_back = ttk.Button(
            play_row, text="-5s", style="Soft.TButton", command=lambda: self._skip(-5.0)
        )
        self.btn_back.grid(row=0, column=0, padx=(0, 8))

        self.btn_play_pause = ttk.Button(
            play_row, text="Play", style="PrimaryMuted.TButton", command=self._play_pause
        )
        self.btn_play_pause.grid(row=0, column=1, padx=(0, 8))

        self.btn_forward = ttk.Button(
            play_row, text="+5s", style="Soft.TButton", command=lambda: self._skip(5.0)
        )
        self.btn_forward.grid(row=0, column=2)

        volume_row = ttk.Frame(controls, style="Card.TFrame")
        volume_row.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        volume_row.columnconfigure(1, weight=1)

        ttk.Label(volume_row, text="Volume", style="Muted.TLabel").grid(row=0, column=0, sticky="w")

        self.vol = ttk.Scale(
            volume_row,
            from_=0.0,
            to=1.0,
            orient="horizontal",
            command=self._on_volume,
            style="Volume.Horizontal.TScale",
        )
        self.vol.grid(row=0, column=1, sticky="ew", padx=10)
        self.vol.bind("<ButtonPress-1>", self._on_volume_press, add="+")
        self.vol.bind("<ButtonRelease-1>", self._on_volume_release, add="+")
        self.vol.set(self.controller.state.volume)
        self.controller.set_volume(self.controller.state.volume)

        self.lbl_volume = ttk.Label(volume_row, text="30%", style="Mono.TLabel")
        self.lbl_volume.grid(row=0, column=2, sticky="e")

        ttk.Label(
            controls,
            text="Shortcuts: Space play/pause, Left/Right seek, Ctrl+Left/Right tempo, Up/Down pitch",
            style="Muted.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(12, 0))

        fx = ttk.Frame(bottom, style="Card.TFrame", padding=18)
        fx.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        fx.columnconfigure(0, weight=1)

        fx_header = ttk.Frame(fx, style="Card.TFrame")
        fx_header.grid(row=0, column=0, sticky="ew")
        fx_header.columnconfigure(0, weight=1)
        ttk.Label(fx_header, text="Playback Effects", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        tempo_row = ttk.Frame(fx, style="Card.TFrame")
        tempo_row.grid(row=1, column=0, sticky="ew", pady=(12, 6))

        ttk.Label(tempo_row, text="Tempo", style="Muted.TLabel").pack(side="left")
        self.btn_reset_tempo = ttk.Button(
            tempo_row,
            text="Reset",
            style="Soft.TButton",
            command=self._reset_tempo,
        )
        self.btn_reset_tempo.pack(side="right", padx=(0, 6))
        self.btn_tempo_down = ttk.Button(
            tempo_row,
            text="-",
            style="Soft.TButton",
            width=3,
            command=lambda: self._nudge_tempo(-1),
        )
        self.btn_tempo_down.pack(side="right", padx=(0, 6))
        self.btn_tempo_up = ttk.Button(
            tempo_row,
            text="+",
            style="Soft.TButton",
            width=3,
            command=lambda: self._nudge_tempo(+1),
        )
        self.btn_tempo_up.pack(side="right", padx=(0, 6))
        self.tempo_display = ttk.Label(tempo_row, text="1.00x", width=8, style="Value.TLabel")
        self.tempo_display.pack(side="right")

        pitch_row = ttk.Frame(fx, style="Card.TFrame")
        pitch_row.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        ttk.Label(pitch_row, text="Pitch", style="Muted.TLabel").pack(side="left")
        self.btn_reset_pitch = ttk.Button(
            pitch_row,
            text="Reset",
            style="Soft.TButton",
            command=self._reset_pitch,
        )
        self.btn_reset_pitch.pack(side="right", padx=(0, 6))
        self.btn_pitch_down = ttk.Button(
            pitch_row,
            text="-",
            style="Soft.TButton",
            width=3,
            command=lambda: self._nudge_pitch(-1),
        )
        self.btn_pitch_down.pack(side="right", padx=(0, 6))
        self.btn_pitch_up = ttk.Button(
            pitch_row,
            text="+",
            style="Soft.TButton",
            width=3,
            command=lambda: self._nudge_pitch(+1),
        )
        self.btn_pitch_up.pack(side="right", padx=(0, 6))
        self.pitch_display = ttk.Label(pitch_row, text="+0 st", width=8, style="Value.TLabel")
        self.pitch_display.pack(side="right")

    def _bind_shortcuts(self):
        self.bind_class(self._shortcut_tag, "<KeyPress-space>", self._on_space_shortcut, add="+")
        self._install_shortcut_tag(self)
        self.bind("<Left>", lambda _e: self._skip(-5.0))
        self.bind("<Right>", lambda _e: self._skip(5.0))
        self.bind("<Control-Left>", lambda _e: self._nudge_tempo(-1))
        self.bind("<Control-Right>", lambda _e: self._nudge_tempo(+1))
        self.bind("<Down>", lambda _e: self._nudge_pitch(-1))
        self.bind("<Up>", lambda _e: self._nudge_pitch(+1))

    def _install_shortcut_tag(self, widget):
        try:
            tags = list(widget.bindtags())
        except Exception:
            return

        if self._shortcut_tag not in tags:
            insert_at = 1 if len(tags) > 1 else len(tags)
            tags.insert(insert_at, self._shortcut_tag)
            widget.bindtags(tuple(tags))

        for child in widget.winfo_children():
            self._install_shortcut_tag(child)

    def _on_space_shortcut(self, event):
        cls = str(event.widget.winfo_class()) if event.widget is not None else ""
        if cls in {"Entry", "TEntry", "Text", "Spinbox", "TSpinbox", "Combobox", "TCombobox"}:
            return None

        self._play_pause()
        return "break"

    def _apply_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_play_pause.configure(state=state)
        self.btn_back.configure(state=state)
        self.btn_forward.configure(state=state)
        self.btn_reset_tempo.configure(state=state)
        self.btn_reset_pitch.configure(state=state)
        self.btn_tempo_down.configure(state=state)
        self.btn_tempo_up.configure(state=state)
        self.btn_pitch_down.configure(state=state)
        self.btn_pitch_up.configure(state=state)
        self.scale.state(["!disabled"] if enabled else ["disabled"])
        self.vol.state(["!disabled"] if enabled else ["disabled"])

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def _set_cover_art(self, cover_bytes: bytes | None):
        if not cover_bytes:
            self.cover_label.configure(image="", text="No cover art")
            self._cover_imgtk = None
            return

        try:
            img = Image.open(io.BytesIO(cover_bytes))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            img.thumbnail((160, 160), resample)
            imgtk = ImageTk.PhotoImage(img)

            self.cover_label.configure(image=imgtk, text="")
            self._cover_imgtk = imgtk
        except Exception:
            self.cover_label.configure(image="", text="Cover art unreadable")
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
        self._update_track_details(st)
        self.lbl_right.configure(text=self._fmt_time(st.duration_s))
        self.lbl_left.configure(text="00:00")
        self.lbl_remaining.configure(text=f"Remaining {self._fmt_time(st.duration_s)}")
        self._set_cover_art(st.cover_bytes)
        self._update_fx_display(st)
        self._update_playback_state(st)

        self._ignore_scale = True
        self.scale.configure(from_=0, to=max(st.duration_s, 1.0))
        self.scale.set(0)
        self._ignore_scale = False

        self.vol.set(st.volume)
        self._refresh_volume_label(st.volume)
        self._apply_enabled(True)

    def _play_pause(self):
        if not self.controller.state.is_loaded:
            return
        self.controller.toggle_play_pause()
        self._update_playback_state(self.controller.state)

    def _skip(self, delta_s: float):
        if not self.controller.state.is_loaded:
            return
        self.controller.skip(delta_s)
        if not self._scrubbing:
            st = self.controller.state
            self.lbl_left.configure(text=self._fmt_time(st.pos_s))
            self._ignore_scale = True
            self.scale.set(st.pos_s)
            self._ignore_scale = False

    def _on_volume(self, _):
        level = float(self.vol.get())
        self.controller.set_volume(level)
        self._refresh_volume_label(level)

    def _on_volume_press(self, event):
        element = ""
        try:
            element = self.vol.identify(event.x, event.y) or ""
        except Exception:
            element = ""

        # Accept direct knob grabs only; ignore trough clicks to avoid hard snaps.
        is_slider_hit = "slider" in element.lower()
        if not is_slider_hit:
            knob_x = self._volume_to_x(float(self.vol.get()))
            is_slider_hit = abs(event.x - knob_x) <= 16

        self._volume_dragging = is_slider_hit
        if not is_slider_hit:
            return "break"
        return None

    def _on_volume_release(self, _event):
        self._volume_dragging = False

    def _volume_to_x(self, value: float) -> int:
        lo = float(self.vol.cget("from"))
        hi = float(self.vol.cget("to"))
        width = max(1, int(self.vol.winfo_width()))
        span = hi - lo
        if span <= 0:
            return width // 2
        ratio = (value - lo) / span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * width))

    def _refresh_volume_label(self, level: float):
        self.lbl_volume.configure(text=f"{int(round(level * 100)):d}%")

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
        self._update_playback_state(self.controller.state)

    def _tick_ui(self):
        self.controller.tick()
        st = self.controller.state

        self._update_playback_state(st)
        self._update_fx_display(st)
        self._refresh_volume_label(st.volume)

        if st.is_loaded and not self._scrubbing:
            self.lbl_left.configure(text=self._fmt_time(st.pos_s))
            self.lbl_right.configure(text=self._fmt_time(st.duration_s))
            remaining = max(0.0, st.duration_s - st.pos_s)
            self.lbl_remaining.configure(text=f"Remaining {self._fmt_time(remaining)}")

            self._ignore_scale = True
            self.scale.configure(to=max(st.duration_s, 1.0))
            self.scale.set(st.pos_s)
            self._ignore_scale = False

        self.after(150, self._tick_ui)

    def _on_close(self):
        try:
            self.controller.shutdown()
        finally:
            self.destroy()

    def _nudge_tempo(self, direction: int):
        if not self.controller.state.is_loaded:
            return

        st = self.controller.state
        new_t = st.tempo + (direction * self._tempo_step)
        new_t = max(self._tempo_min, min(self._tempo_max, new_t))

        self.controller.set_tempo(new_t)
        self._update_fx_display(self.controller.state)

    def _nudge_pitch(self, direction: int):
        if not self.controller.state.is_loaded:
            return

        st = self.controller.state
        new_p = st.semitones + (direction * self._pitch_step)
        new_p = max(self._pitch_min, min(self._pitch_max, new_p))

        self.controller.set_semitones(new_p)
        self._update_fx_display(self.controller.state)

    def _reset_tempo(self):
        if not self.controller.state.is_loaded:
            return
        self.controller.reset_tempo()
        self._update_fx_display(self.controller.state)

    def _reset_pitch(self):
        if not self.controller.state.is_loaded:
            return
        self.controller.reset_pitch()
        self._update_fx_display(self.controller.state)

    def _update_track_details(self, st):
        self.lbl_track_title.configure(text=st.title if st.title else "Unknown track")

        meta_parts = []
        if st.artist:
            meta_parts.append(st.artist)
        if st.album:
            meta_parts.append(st.album)

        if meta_parts:
            self.lbl_track_meta.configure(text=" | ".join(meta_parts))
        else:
            self.lbl_track_meta.configure(text="No artist/album metadata available.")

        self.lbl_header_hint.configure(
            text=f"Track length: {self._fmt_time(st.duration_s)}"
        )

    def _update_fx_display(self, st):
        self.tempo_display.configure(text=f"{st.tempo:.2f}x")
        sign = "+" if st.semitones >= 0 else ""
        self.pitch_display.configure(text=f"{sign}{st.semitones:.0f} st")
        self.status_label.configure(text=st.fx_message or "")

    def _update_playback_state(self, st):
        if not st.is_loaded:
            self.lbl_playback_state.configure(text="Stopped", style="BadgeStop.TLabel")
            self.btn_play_pause.configure(text="Play")
            return

        if st.is_playing and not st.is_paused:
            self.lbl_playback_state.configure(text="Playing", style="BadgePlaying.TLabel")
            self.btn_play_pause.configure(text="Pause")
            return

        if st.is_playing and st.is_paused:
            self.lbl_playback_state.configure(text="Paused", style="BadgePaused.TLabel")
            self.btn_play_pause.configure(text="Resume")
            return

        self.lbl_playback_state.configure(text="Ready", style="BadgeStop.TLabel")
        self.btn_play_pause.configure(text="Play")

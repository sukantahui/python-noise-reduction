"""Interactive Dual Waveform Visualizer displaying Before and After waveforms with metrics and synchronized playhead."""
import tkinter as tk
import customtkinter as ctk
import numpy as np
from typing import Optional, Callable, Tuple, Dict, Any
from src.gui.theme import Theme
from src.core.audio_analyzer import AudioAnalyzer


class WaveformWidget(ctk.CTkFrame):
    """Dual visual waveform comparison widget with real-time seeking playhead and audio quality metrics."""

    def __init__(
        self,
        master: any,
        on_seek: Optional[Callable[[float], None]] = None,
        height: int = 240,
        **kwargs
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.CARD_BG,
            border_color=Theme.CARD_BORDER,
            border_width=1,
            corner_radius=Theme.CORNER_RADIUS_MD,
            height=height,
            **kwargs
        )
        self.on_seek = on_seek

        self.orig_min_env: Optional[np.ndarray] = None
        self.orig_max_env: Optional[np.ndarray] = None
        self.clean_min_env: Optional[np.ndarray] = None
        self.clean_max_env: Optional[np.ndarray] = None

        self.duration: float = 0.0
        self.current_pos_sec: float = 0.0

        self._build_ui()

    def _build_ui(self) -> None:
        # Header Info Bar
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=12, pady=(8, 4))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="📊  Audio Waveform Analysis & Noise Attenuation",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        self.title_label.pack(side="left")

        # Metric Chips
        self.metrics_box = ctk.CTkFrame(self.header_frame, fg_color=Theme.BG_DARK, corner_radius=4)
        self.metrics_box.pack(side="right")

        self.snr_badge = ctk.CTkLabel(
            self.metrics_box,
            text="SNR Gain: -- dB | Noise Floor: -- dBFS",
            font=Theme.FONT_SMALL,
            text_color=Theme.ACCENT_CYAN
        )
        self.snr_badge.pack(side="right", padx=8, pady=2)

        # Tkinter Canvas for high-performance waveform rendering
        self.canvas = tk.Canvas(
            self,
            bg=Theme.CANVAS_BG,
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_click)

    def set_waveforms(
        self,
        orig_audio: np.ndarray,
        clean_audio: Optional[np.ndarray],
        sample_rate: int,
        duration: float,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Computes and stores downsampled waveform envelopes for rendering."""
        self.duration = max(duration, 0.001)

        # Downsample to 1000 points
        self.orig_min_env, self.orig_max_env = AudioAnalyzer.downsample_waveform(orig_audio, num_bins=1000)

        if clean_audio is not None:
            self.clean_min_env, self.clean_max_env = AudioAnalyzer.downsample_waveform(clean_audio, num_bins=1000)
            if metrics is None:
                metrics = AudioAnalyzer.get_audio_metrics(orig_audio, clean_audio, sample_rate)

            snr_gain = metrics["snr_gain_db"]
            noise_att = metrics["noise_attenuation_db"]
            clean_floor = metrics["clean_noise_floor_dbfs"]

            self.snr_badge.configure(
                text=f"✨ SNR Gain: +{snr_gain:.1f} dB  |  Floor: {clean_floor:.1f} dBFS (-{noise_att:.1f} dB cut)"
            )
        else:
            self.clean_min_env, self.clean_max_env = None, None
            self.snr_badge.configure(text="Ready to process")

        self.redraw()

    def update_playhead(self, current_sec: float) -> None:
        self.current_pos_sec = current_sec
        self._draw_playhead()

    def _on_resize(self, event) -> None:
        self.redraw()

    def _on_canvas_click(self, event) -> None:
        if self.duration <= 0:
            return
        width = self.canvas.winfo_width()
        if width > 0:
            ratio = max(0.0, min(1.0, event.x / float(width)))
            target_sec = ratio * self.duration
            if self.on_seek:
                self.on_seek(target_sec)

    def redraw(self) -> None:
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        # Background grid lines & centerlines
        half_h = h / 2.0
        quad1 = h / 4.0
        quad3 = 3.0 * h / 4.0

        # Draw division line between Top (Original Noisy) and Bottom (Denoised Clean)
        self.canvas.create_line(0, half_h, w, half_h, fill="#27272A", width=1, dash=(4, 4))
        self.canvas.create_line(0, quad1, w, quad1, fill="#18181B", width=1)
        self.canvas.create_line(0, quad3, w, quad3, fill="#18181B", width=1)

        # Labels
        self.canvas.create_text(
            10, 12,
            text="ORIGINAL (NOISY TRACK)",
            anchor="w",
            fill=Theme.ACCENT_DIRTY,
            font=("Segoe UI", 9, "bold")
        )
        self.canvas.create_text(
            10, half_h + 12,
            text="DENOISED (CLEAN TRACK)",
            anchor="w",
            fill=Theme.ACCENT_CLEAN,
            font=("Segoe UI", 9, "bold")
        )

        # Render Top: Original Waveform
        if self.orig_min_env is not None and self.orig_max_env is not None:
            self._render_single_waveform(
                min_env=self.orig_min_env,
                max_env=self.orig_max_env,
                center_y=quad1,
                max_amplitude=quad1 * 0.90,
                color=Theme.ACCENT_DIRTY,
                fill_color="#2D1515"
            )

        # Render Bottom: Clean Waveform
        if self.clean_min_env is not None and self.clean_max_env is not None:
            self._render_single_waveform(
                min_env=self.clean_min_env,
                max_env=self.clean_max_env,
                center_y=quad3,
                max_amplitude=quad1 * 0.90,
                color=Theme.ACCENT_CLEAN,
                fill_color="#0F2D1F"
            )
        elif self.orig_min_env is not None:
            # Placeholder text if not yet calculated
            self.canvas.create_text(
                w / 2.0, quad3,
                text="Click 'APPLY & UPDATE PREVIEW' to generate clean output waveform",
                fill=Theme.TEXT_MUTED,
                font=Theme.FONT_BODY
            )

        self._draw_playhead()

    def _render_single_waveform(
        self,
        min_env: np.ndarray,
        max_env: np.ndarray,
        center_y: float,
        max_amplitude: float,
        color: str,
        fill_color: str
    ) -> None:
        w = self.canvas.winfo_width()
        num_points = len(min_env)
        if num_points < 2 or w <= 0:
            return

        # Downsample or step across width
        xs = np.linspace(0, w, num_points)
        top_ys = center_y - (max_env * max_amplitude)
        bot_ys = center_y - (min_env * max_amplitude)

        # Draw vertical slice lines for crisp DAW style rendering
        step = max(1, int(num_points / w))
        for i in range(0, num_points, step):
            x = xs[i]
            y1 = max(center_y - max_amplitude, min(center_y + max_amplitude, top_ys[i]))
            y2 = max(center_y - max_amplitude, min(center_y + max_amplitude, bot_ys[i]))
            if abs(y2 - y1) < 1.0:
                y2 = y1 + 1.0
            self.canvas.create_line(x, y1, x, y2, fill=color, width=1)

    def _draw_playhead(self) -> None:
        self.canvas.delete("playhead")
        if self.duration <= 0:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        playhead_x = (self.current_pos_sec / self.duration) * w

        # Draw glowing playhead vertical cursor line
        self.canvas.create_line(
            playhead_x, 0,
            playhead_x, h,
            fill=Theme.ACCENT_CYAN,
            width=2,
            tags="playhead"
        )
        # Top head triangle marker
        self.canvas.create_polygon(
            playhead_x - 5, 0,
            playhead_x + 5, 0,
            playhead_x, 8,
            fill=Theme.ACCENT_CYAN,
            tags="playhead"
        )

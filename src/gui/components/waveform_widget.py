"""Interactive Dual Waveform Visualizer displaying Before and After waveforms with synchronized playhead."""
import tkinter as tk
import customtkinter as ctk
import numpy as np
from typing import Optional, Callable, Tuple
from src.gui.theme import Theme
from src.core.audio_analyzer import AudioAnalyzer


class WaveformWidget(ctk.CTkFrame):
    """Dual visual waveform comparison widget with real-time seeking playhead."""

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
        self.snr_orig_str: str = "-- dB"
        self.snr_clean_str: str = "-- dB"

        self._build_ui()

    def _build_ui(self) -> None:
        # Header Info Bar
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=12, pady=(8, 4))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="📊  Dual Waveform Analysis (Before vs After)",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        self.title_label.pack(side="left")

        self.snr_badge = ctk.CTkLabel(
            self.header_frame,
            text="SNR: Original [-- dB]  ➔  Cleaned [-- dB]",
            font=Theme.FONT_SMALL,
            text_color=Theme.ACCENT_CYAN
        )
        self.snr_badge.pack(side="right")

        # Tkinter Canvas for high-performance waveform rendering
        self.canvas = tk.Canvas(
            self,
            bg=Theme.CANVAS_BG,
            highlightthickness=0,
            cursor="hand2"
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
        snr_improvement_db: Optional[float] = None
    ) -> None:
        """Computes and stores downsampled waveform envelopes for rendering."""
        self.duration = max(duration, 0.001)

        # Downsample to 1000 points
        self.orig_min_env, self.orig_max_env = AudioAnalyzer.downsample_waveform(orig_audio, num_bins=1000)

        if clean_audio is not None:
            self.clean_min_env, self.clean_max_env = AudioAnalyzer.downsample_waveform(clean_audio, num_bins=1000)
            orig_snr = AudioAnalyzer.estimate_noise_floor_dbfs(orig_audio)
            clean_snr = AudioAnalyzer.estimate_noise_floor_dbfs(clean_audio)
            delta_snr = snr_improvement_db if snr_improvement_db is not None else AudioAnalyzer.estimate_snr_db(orig_audio, clean_audio)
            self.snr_badge.configure(
                text=f"Noise Floor: {orig_snr:.1f} dBFS ➔ {clean_snr:.1f} dBFS | SNR Gain: +{delta_snr:.1f} dB"
            )
        else:
            self.clean_min_env, self.clean_max_env = None, None
            self.snr_badge.configure(text="Processing clean preview...")

        self.redraw()

    def update_playhead(self, current_sec: float) -> None:
        """Updates playhead vertical line position."""
        self.current_pos_sec = current_sec
        self.redraw()

    def redraw(self) -> None:
        """Redraws waveform canvases, grids, centerlines, and playhead."""
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 10 or height <= 10:
            return

        half_h = height / 2.0

        # Draw Divider Line between Top (Original) and Bottom (Clean)
        self.canvas.create_line(0, half_h, width, half_h, fill=Theme.CARD_BORDER, width=1, dash=(4, 4))

        # 1. Draw Top Strip: Original Noisy Waveform
        self.canvas.create_text(
            10, 12,
            anchor="w",
            text="ORIGINAL (NOISY)",
            fill=Theme.ACCENT_DIRTY,
            font=("Segoe UI", 8, "bold")
        )

        top_center_y = half_h / 2.0
        self.canvas.create_line(0, top_center_y, width, top_center_y, fill="#232B3E", width=1)

        if self.orig_min_env is not None and len(self.orig_min_env) > 0:
            self._draw_envelope(
                self.orig_min_env,
                self.orig_max_env,
                width=width,
                center_y=top_center_y,
                max_amplitude_h=half_h * 0.42,
                color=Theme.ACCENT_DIRTY
            )

        # 2. Draw Bottom Strip: Clean Denoised Waveform
        self.canvas.create_text(
            10, half_h + 12,
            anchor="w",
            text="DENOISED (CLEAN)",
            fill=Theme.ACCENT_CLEAN,
            font=("Segoe UI", 8, "bold")
        )

        bot_center_y = half_h + (half_h / 2.0)
        self.canvas.create_line(0, bot_center_y, width, bot_center_y, fill="#232B3E", width=1)

        if self.clean_min_env is not None and len(self.clean_min_env) > 0:
            self._draw_envelope(
                self.clean_min_env,
                self.clean_max_env,
                width=width,
                center_y=bot_center_y,
                max_amplitude_h=half_h * 0.42,
                color=Theme.ACCENT_CLEAN
            )
        elif self.orig_min_env is not None:
            self.canvas.create_text(
                width / 2.0, bot_center_y,
                text="[ Denoising in progress... Click 'Preview Denoise' to update ]",
                fill=Theme.TEXT_MUTED,
                font=Theme.FONT_SMALL
            )

        # 3. Draw Playhead
        if self.duration > 0:
            norm_pos = min(max(self.current_pos_sec / self.duration, 0.0), 1.0)
            playhead_x = norm_pos * width

            # Glow line and main line
            self.canvas.create_line(playhead_x, 0, playhead_x, height, fill=Theme.ACCENT_CYAN, width=2)
            self.canvas.create_polygon(
                playhead_x - 5, 0,
                playhead_x + 5, 0,
                playhead_x, 8,
                fill=Theme.ACCENT_CYAN,
                outline=""
            )

    def _draw_envelope(
        self,
        min_env: np.ndarray,
        max_env: np.ndarray,
        width: float,
        center_y: float,
        max_amplitude_h: float,
        color: str
    ) -> None:
        """Renders vertical bars or polygon fill for waveform envelopes."""
        num_points = len(min_env)
        step = width / float(num_points)

        for i in range(num_points):
            x = i * step
            y_top = center_y - (max_env[i] * max_amplitude_h)
            y_bot = center_y - (min_env[i] * max_amplitude_h)
            # Ensure minimum 1px height
            if abs(y_bot - y_top) < 1.0:
                y_top = center_y - 0.5
                y_bot = center_y + 0.5
            self.canvas.create_line(x, y_top, x, y_bot, fill=color, width=max(1, int(step)))

    def _on_resize(self, event: any) -> None:
        self.redraw()

    def _on_canvas_click(self, event: tk.Event) -> None:
        width = self.canvas.winfo_width()
        if width > 0 and self.duration > 0 and self.on_seek:
            ratio = min(max(event.x / width, 0.0), 1.0)
            target_sec = ratio * self.duration
            self.update_playhead(target_sec)
            self.on_seek(target_sec)

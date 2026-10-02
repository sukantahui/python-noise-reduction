"""Player controls widget providing audio playback, seeking, volume slider, and instant A/B switching."""
import os
import time
import pygame
import customtkinter as ctk
import numpy as np
from pathlib import Path
from typing import Optional, Callable
from src.gui.theme import Theme
from src.utils.temp_manager import TempManager
from src.utils.audio_io import AudioIO
from src.utils.logger import get_logger

logger = get_logger("PlayerControls")


class PlayerControls(ctk.CTkFrame):
    """Interactive audio player bar with gapless A/B comparison switcher."""

    def __init__(
        self,
        master: any,
        on_playhead_update: Optional[Callable[[float], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.CARD_BG,
            border_color=Theme.CARD_BORDER,
            border_width=1,
            corner_radius=Theme.CORNER_RADIUS_MD,
            **kwargs
        )
        self.on_playhead_update = on_playhead_update

        # Audio files for A/B comparison
        self.orig_wav_path: Optional[Path] = None
        self.clean_wav_path: Optional[Path] = None
        self.duration_sec: float = 0.0

        # State
        self.is_playing: bool = False
        self.current_pos_sec: float = 0.0
        self.play_start_timestamp: float = 0.0
        self.ab_mode: str = "B"  # 'A' = Original (Noisy), 'B' = Clean (Denoised)
        self.volume: float = 0.85

        # Initialize Pygame Mixer
        self._init_mixer()
        self._build_ui()
        self._start_timer()

    def _init_mixer(self) -> None:
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.set_volume(self.volume)
        except Exception as ex:
            logger.warning(f"Pygame mixer initialization note: {ex}")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(3, weight=1)

        # 1. Play / Pause Button
        self.play_btn = ctk.CTkButton(
            self,
            text="▶  PLAY",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CYAN,
            hover_color=Theme.ACCENT_CYAN_HOVER,
            text_color="#FFFFFF",
            corner_radius=Theme.CORNER_RADIUS_SM,
            width=100,
            height=36,
            command=self.toggle_play_pause
        )
        self.play_btn.grid(row=0, column=0, padx=(12, 6), pady=10)

        # 2. Stop Button
        self.stop_btn = ctk.CTkButton(
            self,
            text="⏹ STOP",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=Theme.CORNER_RADIUS_SM,
            width=70,
            height=36,
            command=self.stop
        )
        self.stop_btn.grid(row=0, column=1, padx=4, pady=10)

        # 3. Instant A/B Toggle Button
        self.ab_btn = ctk.CTkButton(
            self,
            text="🔁 [B: CLEAN]",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CLEAN,
            hover_color=Theme.ACCENT_CLEAN_HOVER,
            text_color="#FFFFFF",
            corner_radius=Theme.CORNER_RADIUS_SM,
            width=130,
            height=36,
            command=self.toggle_ab_mode
        )
        self.ab_btn.grid(row=0, column=2, padx=6, pady=10)

        # 4. Scrubber & Time Frame
        self.scrub_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.scrub_frame.grid(row=0, column=3, sticky="ew", padx=12, pady=10)
        self.scrub_frame.grid_columnconfigure(1, weight=1)

        self.time_cur_label = ctk.CTkLabel(
            self.scrub_frame,
            text="00:00",
            font=Theme.FONT_MONO,
            text_color=Theme.TEXT_PRIMARY,
            width=45
        )
        self.time_cur_label.grid(row=0, column=0, padx=(0, 6))

        self.scrubber = ctk.CTkSlider(
            self.scrub_frame,
            from_=0.0,
            to=1.0,
            progress_color=Theme.ACCENT_CYAN,
            button_color=Theme.ACCENT_CYAN,
            button_hover_color=Theme.ACCENT_CYAN_HOVER,
            command=self._on_scrubber_drag,
            height=16
        )
        self.scrubber.set(0.0)
        self.scrubber.grid(row=0, column=1, sticky="ew", padx=4)

        self.time_tot_label = ctk.CTkLabel(
            self.scrub_frame,
            text="00:00",
            font=Theme.FONT_MONO,
            text_color=Theme.TEXT_SECONDARY,
            width=45
        )
        self.time_tot_label.grid(row=0, column=2, padx=(6, 0))

        # 5. Volume Slider
        self.vol_label = ctk.CTkLabel(
            self,
            text="🔊",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY
        )
        self.vol_label.grid(row=0, column=4, padx=(6, 2), pady=10)

        self.vol_slider = ctk.CTkSlider(
            self,
            from_=0.0,
            to=1.0,
            width=80,
            progress_color=Theme.ACCENT_CYAN,
            button_color=Theme.ACCENT_CYAN,
            command=self._on_volume_change,
            height=14
        )
        self.vol_slider.set(self.volume)
        self.vol_slider.grid(row=0, column=5, padx=(2, 14), pady=10)

    def load_audio_tracks(
        self,
        orig_array: np.ndarray,
        clean_array: Optional[np.ndarray],
        sample_rate: int,
        duration_sec: float
    ) -> None:
        """Saves memory audio arrays to temporary playback WAVs and resets player."""
        self.stop()
        self.duration_sec = duration_sec

        # Save temporary WAV for original
        if self.orig_wav_path:
            TempManager.remove_file(self.orig_wav_path)
        self.orig_wav_path = TempManager.create_temp_file(suffix=".wav", prefix="orig_play_")
        AudioIO.save_audio(orig_array, sample_rate, self.orig_wav_path)

        # Save temporary WAV for clean if available
        if clean_array is not None:
            if self.clean_wav_path:
                TempManager.remove_file(self.clean_wav_path)
            self.clean_wav_path = TempManager.create_temp_file(suffix=".wav", prefix="clean_play_")
            AudioIO.save_audio(clean_array, sample_rate, self.clean_wav_path)
            self.ab_mode = "B"
            self._update_ab_button()
        else:
            self.clean_wav_path = None
            self.ab_mode = "A"
            self._update_ab_button()

        self.time_tot_label.configure(text=self._format_time(self.duration_sec))
        self.seek(0.0)

    def toggle_play_pause(self) -> None:
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        active_path = self.clean_wav_path if self.ab_mode == "B" and self.clean_wav_path else self.orig_wav_path
        if not active_path or not active_path.exists():
            return

        try:
            pygame.mixer.music.load(str(active_path))
            pygame.mixer.music.play(start=self.current_pos_sec)
            self.play_start_timestamp = time.time() - self.current_pos_sec
            self.is_playing = True
            self.play_btn.configure(text="⏸  PAUSE", fg_color=Theme.ACCENT_AMBER)
        except Exception as ex:
            logger.error(f"Playback error: {ex}")

    def pause(self) -> None:
        if self.is_playing:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
            self.is_playing = False
            self.play_btn.configure(text="▶  PLAY", fg_color=Theme.ACCENT_CYAN)

    def stop(self) -> None:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_playing = False
        self.current_pos_sec = 0.0
        self.play_btn.configure(text="▶  PLAY", fg_color=Theme.ACCENT_CYAN)
        self.scrubber.set(0.0)
        self.time_cur_label.configure(text="00:00")
        if self.on_playhead_update:
            self.on_playhead_update(0.0)

    def seek(self, target_sec: float) -> None:
        target_sec = min(max(target_sec, 0.0), self.duration_sec)
        self.current_pos_sec = target_sec

        if self.duration_sec > 0:
            self.scrubber.set(target_sec / self.duration_sec)
        self.time_cur_label.configure(text=self._format_time(target_sec))

        if self.is_playing:
            self.play()  # Restart at new position

        if self.on_playhead_update:
            self.on_playhead_update(target_sec)

    def toggle_ab_mode(self) -> None:
        """Instantly flips between Original (A) and Clean (B) sound without losing playback position."""
        if not self.clean_wav_path:
            self.ab_mode = "A"
            self._update_ab_button()
            return

        self.ab_mode = "A" if self.ab_mode == "B" else "B"
        self._update_ab_button()

        if self.is_playing:
            # Seamless transition at current exact timestamp
            self.play()

    def _update_ab_button(self) -> None:
        if self.ab_mode == "B" and self.clean_wav_path:
            self.ab_btn.configure(
                text="🔁 [B: CLEAN]",
                fg_color=Theme.ACCENT_CLEAN,
                hover_color=Theme.ACCENT_CLEAN_HOVER
            )
        else:
            self.ab_btn.configure(
                text="🔁 [A: NOISY]",
                fg_color=Theme.ACCENT_DIRTY,
                hover_color=Theme.ACCENT_DIRTY_HOVER
            )

    def _on_scrubber_drag(self, val: float) -> None:
        if self.duration_sec > 0:
            target_sec = val * self.duration_sec
            self.seek(target_sec)

    def _on_volume_change(self, val: float) -> None:
        self.volume = val
        try:
            pygame.mixer.music.set_volume(val)
        except Exception:
            pass

    def _start_timer(self) -> None:
        """Polls every 50ms to update scrubber and playhead position smoothly."""
        if self.is_playing:
            cur = time.time() - self.play_start_timestamp
            if cur >= self.duration_sec:
                self.stop()
            else:
                self.current_pos_sec = cur
                if self.duration_sec > 0:
                    self.scrubber.set(cur / self.duration_sec)
                self.time_cur_label.configure(text=self._format_time(cur))
                if self.on_playhead_update:
                    self.on_playhead_update(cur)

        self.after(40, self._start_timer)

    @staticmethod
    def _format_time(seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

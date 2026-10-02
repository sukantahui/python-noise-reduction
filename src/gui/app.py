"""Main application window and controller for NoiseRelief Studio."""
import sys
import threading
import webbrowser
import customtkinter as ctk
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from src.gui.theme import Theme
from src.gui.components.drop_zone import DropZone
from src.gui.components.waveform_widget import WaveformWidget
from src.gui.components.player_controls import PlayerControls
from src.gui.components.settings_panel import SettingsPanel
from src.gui.components.batch_queue_view import BatchQueueView
from src.gui.components.about_dialog import AboutDialog
from src.gui.components.extract_dialog import ExtractAudioDialog
from src.gui.components.video_splitter_dialog import VideoSplitterDialog
from src.gui.components.audio_splitter_dialog import AudioSplitterDialog

from src.core.audio_engine import AudioDenoiseEngine, DenoiseConfig
from src.core.video_engine import VideoEngine
from src.core.audio_analyzer import AudioAnalyzer
from src.utils.audio_io import AudioIO
from src.utils.ffmpeg_helper import FFmpegHelper
from src.utils.temp_manager import TempManager
from src.utils.logger import get_logger

logger = get_logger("App")


class NoiseReliefApp(ctk.CTk):
    """NoiseRelief Studio Main Window."""

    def __init__(self) -> None:
        super().__init__()

        # Appearance & Window Configuration
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("CNAT NOISERELIEF — Audio & Video Noise Reduction (by Coder & AccoTax)")
        self.geometry("1280x820")
        self.minsize(1024, 700)
        self.configure(fg_color=Theme.BG_DARK)

        # Set Window Icon
        self._set_window_icon()

        # Worker Thread Pool
        self.executor = ThreadPoolExecutor(max_workers=3)

        # Current Working State
        self.current_media_path: Optional[Path] = None
        self.current_raw_audio: Optional[np.ndarray] = None
        self.current_clean_audio: Optional[np.ndarray] = None
        self.sample_rate: int = 48000
        self.duration_sec: float = 0.0

        self._build_layout()
        self._bind_shortcuts()

    def _set_window_icon(self) -> None:
        """Sets application window icon from assets."""
        try:
            icon_path = Path(__file__).parent / "assets" / "logo.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception as ex:
            logger.debug(f"Could not set window icon: {ex}")

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        # -------------------------------------------------------------
        # Top App Title & Branding Banner
        # -------------------------------------------------------------
        self.title_banner = ctk.CTkFrame(self, fg_color="transparent")
        self.title_banner.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 4))
        
        # Left side: Logo + Title + Subtitle
        self.brand_left = ctk.CTkFrame(self.title_banner, fg_color="transparent")
        self.brand_left.pack(side="left", fill="y")

        logo_path = Path(__file__).parent / "assets" / "logo.png"
        if not logo_path.exists():
            logo_path = Path("assets/logo.png")

        if logo_path.exists():
            try:
                pil_logo = Image.open(logo_path)
                self.logo_ctk = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(34, 34))
                self.logo_label = ctk.CTkLabel(self.brand_left, image=self.logo_ctk, text="")
                self.logo_label.pack(side="left", padx=(0, 8))
            except Exception:
                pass

        self.title_text_box = ctk.CTkFrame(self.brand_left, fg_color="transparent")
        self.title_text_box.pack(side="left")

        self.app_heading = ctk.CTkLabel(
            self.title_text_box,
            text="CNAT NOISERELIEF",
            font=("Segoe UI", 16, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w"
        )
        self.app_heading.pack(anchor="w")

        self.app_subheading = ctk.CTkLabel(
            self.title_text_box,
            text="AI-Enhanced Spectral Denoising, Audio/Video Splitting & Remuxing",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY,
            anchor="w"
        )
        self.app_subheading.pack(anchor="w")

        # Right side: Creator Attribution & Contact Info (Coder & AccoTax)
        self.brand_right = ctk.CTkFrame(
            self.title_banner,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.brand_right.pack(side="right", fill="y", pady=2)

        self.creator_label = ctk.CTkLabel(
            self.brand_right,
            text="Created by Coder & AccoTax",
            font=("Segoe UI", 10, "bold"),
            text_color=Theme.ACCENT_CYAN
        )
        self.creator_label.pack(side="left", padx=(10, 6), pady=4)

        self.website_btn = ctk.CTkButton(
            self.brand_right,
            text="🌐 www.codernaccotax.co.in",
            font=("Segoe UI", 10, "underline"),
            fg_color="transparent",
            hover_color=Theme.CARD_BG_HOVER,
            text_color=Theme.TEXT_PRIMARY,
            cursor="hand2",
            height=22,
            command=lambda: webbrowser.open_new_tab("https://www.codernaccotax.co.in")
        )
        self.website_btn.pack(side="left", padx=4, pady=4)

        self.phone_label = ctk.CTkLabel(
            self.brand_right,
            text="📞 7003756860",
            font=("Segoe UI", 10, "bold"),
            text_color=Theme.TEXT_SECONDARY
        )
        self.phone_label.pack(side="left", padx=(4, 8), pady=4)

        self.about_btn = ctk.CTkButton(
            self.brand_right,
            text="ℹ️ About",
            font=("Segoe UI", 10, "bold"),
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color=Theme.TEXT_PRIMARY,
            width=65,
            height=22,
            corner_radius=4,
            command=self._open_about_dialog
        )
        self.about_btn.pack(side="left", padx=(0, 6), pady=4)

        # -------------------------------------------------------------
        # Left Main Work Area (DropZone, Waveforms, Player)
        # -------------------------------------------------------------
        self.left_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.left_frame.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=6)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=1)

        # Drop Zone
        self.drop_zone = DropZone(
            self.left_frame,
            on_file_selected=self._on_media_loaded,
            on_extract_audio=self._open_extract_dialog,
            on_split_video=self._open_video_splitter_dialog,
            on_split_audio=self._open_audio_splitter_dialog
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # Dual Waveform Display
        self.waveform_widget = WaveformWidget(
            self.left_frame,
            on_seek=self._on_waveform_seek
        )
        self.waveform_widget.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        # Player Controls Bar
        self.player_controls = PlayerControls(
            self.left_frame,
            on_playhead_update=self.waveform_widget.update_playhead
        )
        self.player_controls.grid(row=2, column=0, sticky="ew", pady=(0, 0))

        # -------------------------------------------------------------
        # Right Settings & Preset Panel
        # -------------------------------------------------------------
        self.settings_panel = SettingsPanel(
            self,
            on_settings_change=self._on_settings_changed,
            on_preview_request=self._recalculate_denoise_preview
        )
        self.settings_panel.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=6)

        # -------------------------------------------------------------
        # Bottom Export & Batch Panel
        # -------------------------------------------------------------
        self.export_view = BatchQueueView(
            self,
            on_export_start=self._on_export_requested,
            on_extract_audio_request=lambda: self._open_extract_dialog(self.current_media_path),
            on_split_video_request=lambda: self._open_video_splitter_dialog(self.current_media_path),
            on_split_audio_request=lambda: self._open_audio_splitter_dialog(self.current_media_path)
        )
        self.export_view.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(6, 14))

    def _bind_shortcuts(self) -> None:
        self.bind("<space>", lambda e: self.player_controls.toggle_play_pause())
        self.bind("<Tab>", lambda e: self.player_controls.toggle_ab_mode())
        self.bind("<Control-o>", lambda e: self.drop_zone._on_browse_click())

    def _on_media_loaded(self, file_path: Path) -> None:
        """Handles incoming audio or video file selection."""
        self.current_media_path = file_path
        self.export_view.update_progress(10.0, f"Loading {file_path.name}...")

        def _worker():
            try:
                # 1. Load Audio Array
                if FFmpegHelper.is_video_file(file_path):
                    self._dispatch_ui(lambda: self.export_view.update_progress(20.0, "Extracting video audio stream..."))
                    temp_wav = VideoEngine.extract_audio(file_path, sample_rate=48000)
                    audio_arr, sr = AudioIO.load_audio(temp_wav)
                    TempManager.remove_file(temp_wav)
                else:
                    self._dispatch_ui(lambda: self.export_view.update_progress(25.0, "Decoding audio file..."))
                    audio_arr, sr = AudioIO.load_audio(file_path)

                self.current_raw_audio = audio_arr
                self.sample_rate = sr
                self.duration_sec = audio_arr.shape[-1] / float(sr)

                # 2. Update dropzone metadata
                meta_str = f"{sr/1000.0:.1f} kHz | {'Stereo' if audio_arr.ndim > 1 else 'Mono'} | {PlayerControls._format_time(self.duration_sec)}"
                self._dispatch_ui(lambda: self.drop_zone.set_loaded_file(file_path, meta_str))

                # 3. Calculate initial clean preview in background
                self._dispatch_ui(lambda: self.export_view.update_progress(50.0, "Calculating spectral noise profile..."))
                config = self.settings_panel.get_config()
                clean_arr = AudioDenoiseEngine.process_audio(
                    audio=audio_arr,
                    sample_rate=sr,
                    config=config
                )
                self.current_clean_audio = clean_arr

                # 4. Dispatch updates to Waveform and Player
                self._dispatch_ui(lambda: self._apply_loaded_tracks(audio_arr, clean_arr, sr, self.duration_sec))
                self._dispatch_ui(lambda: self.export_view.update_progress(100.0, "Media loaded and ready for playback."))
            except Exception as ex:
                logger.error(f"Failed to load media file: {ex}")
                self._dispatch_ui(lambda: self.export_view.update_progress(0.0, f"Error: {ex}"))

        self.executor.submit(_worker)

    def _apply_loaded_tracks(self, orig_arr: np.ndarray, clean_arr: np.ndarray, sr: int, duration: float) -> None:
        self.waveform_widget.set_waveforms(orig_arr, clean_arr, sr, duration)
        self.player_controls.load_audio_tracks(orig_arr, clean_arr, sr, duration)

    def _on_waveform_seek(self, target_sec: float) -> None:
        self.player_controls.seek(target_sec)

    def _on_settings_changed(self, new_config: DenoiseConfig) -> None:
        # Settings updated; ready to re-render preview
        pass

    def _recalculate_denoise_preview(self) -> None:
        """Re-applies DSP parameters to raw audio and refreshes waveform/player in real-time."""
        if self.current_raw_audio is None:
            return

        self.export_view.update_progress(30.0, "Re-calculating noise suppression...")

        def _worker():
            try:
                config = self.settings_panel.get_config()
                clean_arr = AudioDenoiseEngine.process_audio(
                    audio=self.current_raw_audio,
                    sample_rate=self.sample_rate,
                    config=config
                )
                self.current_clean_audio = clean_arr

                self._dispatch_ui(lambda: self.waveform_widget.set_waveforms(
                    self.current_raw_audio,
                    clean_arr,
                    self.sample_rate,
                    self.duration_sec
                ))
                self._dispatch_ui(lambda: self.player_controls.load_audio_tracks(
                    self.current_raw_audio,
                    clean_arr,
                    self.sample_rate,
                    self.duration_sec
                ))
                self._dispatch_ui(lambda: self.export_view.update_progress(100.0, "Preview updated successfully."))
            except Exception as ex:
                logger.error(f"Error recalculating preview: {ex}")
                self._dispatch_ui(lambda: self.export_view.update_progress(0.0, f"Preview Error: {ex}"))

        self.executor.submit(_worker)

    def _on_export_requested(self, output_dir: Path, video_mode: str, suffix: str) -> None:
        """Executes full high-fidelity export of cleaned audio or video."""
        if not self.current_media_path or self.current_raw_audio is None:
            self.export_view.update_progress(0.0, "No media file loaded to export.")
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        config = self.settings_panel.get_config()
        src_path = self.current_media_path

        def _export_worker():
            try:
                self._dispatch_ui(lambda: self.export_view.update_progress(10.0, "Starting export processing..."))

                def _progress_cb(pct: float, msg: str):
                    self._dispatch_ui(lambda: self.export_view.update_progress(pct, msg))

                stem = src_path.stem
                is_vid = FFmpegHelper.is_video_file(src_path)

                if is_vid and "Video Remux" in video_mode:
                    # Export Lossless Remuxed Video
                    out_video_name = f"{stem}_cleaned{src_path.suffix}"
                    out_path = output_dir / out_video_name
                    VideoEngine.process_video_file(
                        video_path=src_path,
                        output_video_path=out_path,
                        config=config,
                        progress_callback=_progress_cb
                    )
                elif "Raw Original Audio" in video_mode:
                    # Export original audio track directly from media
                    if "MP3" in video_mode:
                        out_audio_name = f"{stem}_original.mp3"
                    elif "FLAC" in video_mode:
                        out_audio_name = f"{stem}_original.flac"
                    else:
                        out_audio_name = f"{stem}_original.wav"

                    out_path = output_dir / out_audio_name
                    if is_vid:
                        VideoEngine.extract_sound(
                            video_path=src_path,
                            output_audio_path=out_path,
                            denoise=False,
                            progress_callback=_progress_cb
                        )
                    else:
                        AudioIO.save_audio(self.current_raw_audio, self.sample_rate, out_path)
                    _progress_cb(100.0, f"Exported: {out_path.name}")
                elif "Noise Track Only" in video_mode:
                    # Export isolated noise profile (Delta)
                    if self.current_clean_audio is None:
                        clean_audio = AudioDenoiseEngine.process_audio(
                            audio=self.current_raw_audio,
                            sample_rate=self.sample_rate,
                            config=config,
                            progress_callback=_progress_cb
                        )
                    else:
                        clean_audio = self.current_clean_audio

                    min_len = min(self.current_raw_audio.shape[-1], clean_audio.shape[-1])
                    delta_audio = self.current_raw_audio[..., :min_len] - clean_audio[..., :min_len]
                    out_audio_name = f"{stem}_noise_track.wav"
                    out_path = output_dir / out_audio_name
                    AudioIO.save_audio(delta_audio, self.sample_rate, out_path)
                    _progress_cb(100.0, f"Exported Noise Track: {out_path.name}")
                else:
                    # Export Cleaned Audio (WAV, MP3, FLAC, AAC, OGG)
                    if self.current_clean_audio is None:
                        clean_audio = AudioDenoiseEngine.process_audio(
                            audio=self.current_raw_audio,
                            sample_rate=self.sample_rate,
                            config=config,
                            progress_callback=_progress_cb
                        )
                    else:
                        clean_audio = self.current_clean_audio

                    if "MP3" in video_mode or src_path.suffix.lower() == ".mp3":
                        out_audio_name = f"{stem}_cleaned.mp3"
                    elif "FLAC" in video_mode or src_path.suffix.lower() == ".flac":
                        out_audio_name = f"{stem}_cleaned.flac"
                    elif "AAC" in video_mode or "M4A" in video_mode:
                        out_audio_name = f"{stem}_cleaned.m4a"
                    elif "OGG" in video_mode or src_path.suffix.lower() == ".ogg":
                        out_audio_name = f"{stem}_cleaned.ogg"
                    else:
                        out_audio_name = f"{stem}_cleaned.wav"

                    out_path = output_dir / out_audio_name
                    AudioIO.save_audio(clean_audio, self.sample_rate, out_path)
                    _progress_cb(100.0, f"Exported: {out_path.name}")

                self._dispatch_ui(lambda: self.export_view.update_progress(100.0, f"Successfully exported: {out_path.name}"))
            except Exception as ex:
                logger.error(f"Export failed: {ex}")
                self._dispatch_ui(lambda: self.export_view.update_progress(0.0, f"Export Failed: {ex}"))

        self.executor.submit(_export_worker)

    def _open_extract_dialog(self, target_video_path: Optional[Path] = None) -> None:
        """Opens the Extract Sound from Video modal dialog."""
        target_video = target_video_path or self.current_media_path
        config = self.settings_panel.get_config()
        ExtractAudioDialog(
            parent=self,
            default_video_path=target_video,
            denoise_config=config,
            on_success=lambda p: self.export_view.update_progress(100.0, f"Extracted: {p.name}")
        )

    def _open_video_splitter_dialog(self, target_video_path: Optional[Path] = None) -> None:
        """Opens the Video Splitter & Trimmer modal dialog."""
        target_video = target_video_path or self.current_media_path
        config = self.settings_panel.get_config()
        VideoSplitterDialog(
            parent=self,
            default_video_path=target_video,
            denoise_config=config,
            on_success=lambda files: self.export_view.update_progress(100.0, f"Split into {len(files)} video clips")
        )

    def _open_audio_splitter_dialog(self, target_audio_path: Optional[Path] = None) -> None:
        """Opens the Audio Splitter & Silence Cutter modal dialog."""
        target_audio = target_audio_path or self.current_media_path
        config = self.settings_panel.get_config()
        AudioSplitterDialog(
            parent=self,
            default_audio_path=target_audio,
            denoise_config=config,
            on_success=lambda files: self.export_view.update_progress(100.0, f"Split into {len(files)} audio tracks")
        )

    def _open_about_dialog(self) -> None:
        """Opens the About dialog modal."""
        AboutDialog(self)

    def _dispatch_ui(self, func) -> None:
        """Thread-safe UI callback scheduling on main Tkinter thread."""
        self.after(0, func)

    def destroy(self) -> None:
        """Clean shutdown of threads and audio mixer."""
        try:
            self.player_controls.stop()
            pygame.mixer.quit()
        except Exception:
            pass
        self.executor.shutdown(wait=False)
        TempManager.cleanup_all()
        super().destroy()

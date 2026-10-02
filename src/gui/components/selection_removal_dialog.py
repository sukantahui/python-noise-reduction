"""Selection Removal & Segment Cutting Dialog for Audio and Video in CNAT NOISERELIEF."""
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from tkinter import filedialog
import customtkinter as ctk

from src.gui.theme import Theme
from src.utils.ffmpeg_helper import FFmpegHelper
from src.utils.audio_io import AudioIO
from src.core.audio_engine import AudioDenoiseEngine, DenoiseConfig
from src.core.video_engine import VideoEngine
from src.utils.logger import get_logger

logger = get_logger("SelectionRemovalDialog")


class SelectionRemovalDialog(ctk.CTkToplevel):
    """Modern modal dialog for cutting out or muting a selected time interval from Audio or Video files."""

    def __init__(
        self,
        parent: ctk.CTk,
        default_media_path: Optional[Path] = None,
        denoise_config: Optional[DenoiseConfig] = None,
        on_success: Optional[Callable[[Path], None]] = None
    ) -> None:
        super().__init__(parent)

        self.title("✂️ Remove / Cut Selected Region — CNAT NOISERELIEF")
        self.geometry("640x700")
        self.minsize(600, 640)
        self.configure(fg_color=Theme.BG_DARK)

        # Modal configuration
        self.transient(parent)
        self.grab_set()

        self.default_media_path = default_media_path
        self.denoise_config = denoise_config or DenoiseConfig()
        self.on_success = on_success
        self.is_processing = False
        self.media_duration: float = 0.0
        self.is_video: bool = False

        self._center_window(parent)
        self._build_ui()

        if self.default_media_path and self.default_media_path.exists():
            self._set_selected_media(self.default_media_path)

    def _center_window(self, parent: ctk.CTk) -> None:
        parent.update_idletasks()
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        w, h = 640, 700
        x = max(0, p_x + (p_w - w) // 2)
        y = max(0, p_y + (p_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Scrollable container for dialog content
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 1. Header Banner
        self.header_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.header_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self.header_title = ctk.CTkLabel(
            self.header_card,
            text="✂️ Audio & Video Selection Removal / Muter",
            font=Theme.FONT_SUBHEADING,
            text_color=Theme.TEXT_PRIMARY
        )
        self.header_title.pack(anchor="w", padx=14, pady=(10, 2))

        self.header_desc = ctk.CTkLabel(
            self.header_card,
            text="Cut out unwanted sections, profanity, dead air, or mute specific intervals from media tracks.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.header_desc.pack(anchor="w", padx=14, pady=(0, 10))

        # 2. Media File Selector
        self.file_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.file_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.file_card.grid_columnconfigure(0, weight=1)

        self.file_label = ctk.CTkLabel(
            self.file_card,
            text="📁 Source Media File (Audio or Video)",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.ACCENT_CYAN
        )
        self.file_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        self.file_path_var = ctk.StringVar(value="No file selected")
        self.file_entry = ctk.CTkEntry(
            self.file_card,
            textvariable=self.file_path_var,
            font=Theme.FONT_SMALL,
            state="readonly"
        )
        self.file_entry.grid(row=1, column=0, sticky="ew", padx=(14, 8), pady=(0, 8))

        self.browse_btn = ctk.CTkButton(
            self.file_card,
            text="Browse...",
            width=90,
            command=self._on_browse_file
        )
        self.browse_btn.grid(row=1, column=1, padx=(0, 14), pady=(0, 8))

        self.meta_label = ctk.CTkLabel(
            self.file_card,
            text="Duration: 00:00:00 | Type: None",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED
        )
        self.meta_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 10))

        # 3. Removal Action Mode
        self.action_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.action_card.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self.action_label = ctk.CTkLabel(
            self.action_card,
            text="⚙️ Action for Selected Region",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_PRIMARY
        )
        self.action_label.pack(anchor="w", padx=14, pady=(10, 6))

        self.action_var = ctk.StringVar(value="cut")
        self.radio_cut = ctk.CTkRadioButton(
            self.action_card,
            text="✂️ Cut Out & Join Remaining Parts (Deletes the selected range and splices the rest)",
            variable=self.action_var,
            value="cut",
            font=Theme.FONT_BODY
        )
        self.radio_cut.pack(anchor="w", padx=14, pady=(0, 6))

        self.radio_mute = ctk.CTkRadioButton(
            self.action_card,
            text="🔇 Mute / Silence Audio in Selection (Keeps media duration, sets volume to 0 in range)",
            variable=self.action_var,
            value="mute",
            font=Theme.FONT_BODY
        )
        self.radio_mute.pack(anchor="w", padx=14, pady=(0, 10))

        # 4. Selection Range Specification
        self.range_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.range_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self.range_card.grid_columnconfigure(1, weight=1)
        self.range_card.grid_columnconfigure(3, weight=1)

        self.range_title = ctk.CTkLabel(
            self.range_card,
            text="⏱️ Time Range to Remove / Mute",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_PRIMARY
        )
        self.range_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(10, 8))

        self.start_label = ctk.CTkLabel(self.range_card, text="Start Time:", font=Theme.FONT_BODY)
        self.start_label.grid(row=1, column=0, sticky="w", padx=(14, 6), pady=(0, 8))

        self.start_var = ctk.StringVar(value="00:00:00.0")
        self.start_entry = ctk.CTkEntry(self.range_card, textvariable=self.start_var, font=Theme.FONT_BODY)
        self.start_entry.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 8))

        self.end_label = ctk.CTkLabel(self.range_card, text="End Time:", font=Theme.FONT_BODY)
        self.end_label.grid(row=1, column=2, sticky="w", padx=(6, 6), pady=(0, 8))

        self.end_var = ctk.StringVar(value="00:00:05.0")
        self.end_entry = ctk.CTkEntry(self.range_card, textvariable=self.end_var, font=Theme.FONT_BODY)
        self.end_entry.grid(row=1, column=3, sticky="ew", padx=(0, 14), pady=(0, 8))

        # Quick Preset Buttons Frame
        self.quick_btn_frame = ctk.CTkFrame(self.range_card, fg_color="transparent")
        self.quick_btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 10))

        presets = [
            ("First 5s", lambda: self._apply_preset_range(0.0, 5.0)),
            ("First 10s", lambda: self._apply_preset_range(0.0, 10.0)),
            ("First 30s", lambda: self._apply_preset_range(0.0, 30.0)),
            ("Last 5s", lambda: self._apply_last_preset(5.0)),
            ("Last 10s", lambda: self._apply_last_preset(10.0)),
            ("Last 30s", lambda: self._apply_last_preset(30.0)),
        ]
        for name, cmd in presets:
            btn = ctk.CTkButton(
                self.quick_btn_frame,
                text=name,
                font=("Segoe UI", 10),
                height=24,
                fg_color=Theme.CARD_BG_HOVER,
                hover_color=Theme.CARD_BORDER,
                command=cmd
            )
            btn.pack(side="left", padx=2)

        # 5. DSP Noise Reduction Toggle & Crossfade
        self.opt_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.opt_card.grid(row=4, column=0, sticky="ew", pady=(0, 12))

        self.denoise_toggle_var = ctk.BooleanVar(value=False)
        self.denoise_chk = ctk.CTkCheckBox(
            self.opt_card,
            text="✨ Clean Background Noise in remaining audio output",
            variable=self.denoise_toggle_var,
            font=Theme.FONT_BODY,
            text_color=Theme.ACCENT_CYAN
        )
        self.denoise_chk.pack(anchor="w", padx=14, pady=(10, 10))

        # 6. Output Destination
        self.dest_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.dest_card.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        self.dest_card.grid_columnconfigure(0, weight=1)

        self.dest_label = ctk.CTkLabel(
            self.dest_card,
            text="📁 Destination Output Directory",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_PRIMARY
        )
        self.dest_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        default_out = Path.home() / "Music" / "CNAT_NoiseRelief_Cuts"
        self.dest_path_var = ctk.StringVar(value=str(default_out))
        self.dest_entry = ctk.CTkEntry(
            self.dest_card,
            textvariable=self.dest_path_var,
            font=Theme.FONT_SMALL
        )
        self.dest_entry.grid(row=1, column=0, sticky="ew", padx=(14, 8), pady=(0, 10))

        self.dest_browse_btn = ctk.CTkButton(
            self.dest_card,
            text="Choose...",
            width=90,
            command=self._on_browse_dest
        )
        self.dest_browse_btn.grid(row=1, column=1, padx=(0, 14), pady=(0, 10))

        # 7. Progress & Action Buttons
        self.progress_bar = ctk.CTkProgressBar(
            self.scroll_frame,
            height=8,
            progress_color=Theme.ACCENT_CYAN
        )
        self.progress_bar.grid(row=6, column=0, sticky="ew", pady=(0, 6))
        self.progress_bar.set(0.0)

        self.status_label = ctk.CTkLabel(
            self.scroll_frame,
            text="Ready to remove selection.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.status_label.grid(row=7, column=0, sticky="w", pady=(0, 10))

        self.btn_action_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.btn_action_frame.grid(row=8, column=0, sticky="ew")

        self.cancel_btn = ctk.CTkButton(
            self.btn_action_frame,
            text="Close",
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            command=self.destroy
        )
        self.cancel_btn.pack(side="left", padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            self.btn_action_frame,
            text="📂 Open Output Folder",
            fg_color=Theme.CARD_BG,
            hover_color=Theme.CARD_BG_HOVER,
            command=self._on_open_folder,
            state="disabled"
        )
        self.open_folder_btn.pack(side="left")

        self.start_btn = ctk.CTkButton(
            self.btn_action_frame,
            text="✂️ Process & Remove Selection",
            fg_color=Theme.ACCENT_CYAN,
            text_color="#000000",
            font=Theme.FONT_BODY_BOLD,
            hover_color="#0891B2",
            command=self._on_start_processing
        )
        self.start_btn.pack(side="right")

    def _on_browse_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Audio or Video File",
            filetypes=[
                ("All Supported Media", "*.mp4;*.mkv;*.mov;*.avi;*.webm;*.wav;*.mp3;*.flac;*.aac;*.m4a;*.ogg"),
                ("Video Files", "*.mp4;*.mkv;*.mov;*.avi;*.webm"),
                ("Audio Files", "*.wav;*.mp3;*.flac;*.aac;*.m4a;*.ogg"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self._set_selected_media(Path(file_path))

    def _set_selected_media(self, path: Path) -> None:
        self.default_media_path = path
        self.file_path_var.set(str(path))
        self.is_video = FFmpegHelper.is_video_file(path)

        # Get duration
        try:
            if self.is_video:
                self.media_duration = FFmpegHelper.get_media_duration(path)
                m_type = f"Video ({path.suffix.upper()})"
            else:
                arr, sr = AudioIO.load_audio(path)
                self.media_duration = arr.shape[-1] / float(sr)
                m_type = f"Audio ({path.suffix.upper()}) | {sr/1000.0:.1f}kHz"

            self.meta_label.configure(
                text=f"Duration: {self._format_time(self.media_duration)} ({self.media_duration:.2f}s) | Type: {m_type}"
            )
            # Default end time = 5s or 1/4th duration
            init_end = min(self.media_duration, max(1.0, self.media_duration * 0.25))
            self.end_var.set(self._format_time(init_end))
        except Exception as ex:
            self.meta_label.configure(text=f"Error reading media: {ex}")

    def _apply_preset_range(self, start: float, end: float) -> None:
        if self.media_duration > 0:
            start = max(0.0, min(self.media_duration, start))
            end = max(start + 0.1, min(self.media_duration, end))
            self.start_var.set(self._format_time(start))
            self.end_var.set(self._format_time(end))

    def _apply_last_preset(self, seconds: float) -> None:
        if self.media_duration > 0:
            start = max(0.0, self.media_duration - seconds)
            end = self.media_duration
            self.start_var.set(self._format_time(start))
            self.end_var.set(self._format_time(end))

    def _on_browse_dest(self) -> None:
        d = filedialog.askdirectory(title="Select Destination Directory")
        if d:
            self.dest_path_var.set(d)

    def _on_open_folder(self) -> None:
        out_dir = self.dest_path_var.get().strip()
        if out_dir and os.path.exists(out_dir):
            if sys.platform == "win32":
                os.startfile(out_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out_dir])
            else:
                subprocess.Popen(["xdg-open", out_dir])

    def _parse_time_str(self, t_str: str) -> float:
        """Parses HH:MM:SS or SS.S into seconds."""
        t_str = t_str.strip()
        if not t_str:
            return 0.0
        parts = t_str.split(":")
        if len(parts) == 3:
            h = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m = float(parts[0])
            s = float(parts[1])
            return m * 60 + s
        else:
            return float(t_str)

    @staticmethod
    def _format_time(sec: float) -> str:
        s = max(0.0, sec)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        remaining_s = s % 60
        return f"{h:02d}:{m:02d}:{remaining_s:04.1f}"

    def _on_start_processing(self) -> None:
        if self.is_processing:
            return

        in_path_str = self.file_path_var.get()
        if not in_path_str or in_path_str == "No file selected":
            self.status_label.configure(text="Please select a media file first.", text_color=Theme.ACCENT_RED)
            return

        in_path = Path(in_path_str)
        if not in_path.exists():
            self.status_label.configure(text="Selected file does not exist.", text_color=Theme.ACCENT_RED)
            return

        try:
            start_sec = self._parse_time_str(self.start_var.get())
            end_sec = self._parse_time_str(self.end_var.get())
        except ValueError:
            self.status_label.configure(text="Invalid time format. Use HH:MM:SS or seconds.", text_color=Theme.ACCENT_RED)
            return

        if end_sec <= start_sec:
            self.status_label.configure(text="End time must be greater than start time.", text_color=Theme.ACCENT_RED)
            return

        out_dir = Path(self.dest_path_var.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)

        action_mode = self.action_var.get()
        denoise_flag = self.denoise_toggle_var.get()

        # Output filename
        tag = "muted" if action_mode == "mute" else "cut"
        out_name = f"{in_path.stem}_{tag}{in_path.suffix}"
        dest_file = out_dir / out_name

        self.is_processing = True
        self.start_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress_bar.set(0.1)

        def _worker():
            try:
                def _prog(pct: float, msg: str):
                    self.after(0, lambda: self._update_progress(pct, msg))

                if self.is_video:
                    act = "mute_audio" if action_mode == "mute" else "cut"
                    res = VideoEngine.remove_video_selection(
                        video_path=in_path,
                        start_sec=start_sec,
                        end_sec=end_sec,
                        output_path=dest_file,
                        action=act,
                        denoise=denoise_flag,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )
                else:
                    res = AudioDenoiseEngine.remove_audio_selection(
                        audio_path=in_path,
                        start_sec=start_sec,
                        end_sec=end_sec,
                        output_path=dest_file,
                        action=action_mode,
                        denoise=denoise_flag,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )

                self.after(0, lambda: self._on_complete(res))
            except Exception as ex:
                logger.error(f"Selection removal failed: {ex}")
                self.after(0, lambda: self._on_error(str(ex)))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, pct: float, msg: str) -> None:
        self.progress_bar.set(pct / 100.0)
        self.status_label.configure(text=msg, text_color=Theme.TEXT_SECONDARY)

    def _on_complete(self, output_file: Path) -> None:
        self.is_processing = False
        self.start_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self.progress_bar.set(1.0)
        self.status_label.configure(
            text=f"✅ Done! Saved: {output_file.name}",
            text_color=Theme.ACCENT_GREEN
        )
        if self.on_success:
            self.on_success(output_file)

    def _on_error(self, err_msg: str) -> None:
        self.is_processing = False
        self.start_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.progress_bar.set(0.0)
        self.status_label.configure(
            text=f"❌ Error: {err_msg}",
            text_color=Theme.ACCENT_RED
        )

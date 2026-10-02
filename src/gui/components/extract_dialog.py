"""Dedicated modal dialog for extracting sound/audio tracks from video files."""
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from tkinter import filedialog
import customtkinter as ctk

from src.gui.theme import Theme
from src.core.video_engine import VideoEngine
from src.core.audio_engine import DenoiseConfig
from src.utils.ffmpeg_helper import FFmpegHelper
from src.utils.logger import get_logger

logger = get_logger("ExtractAudioDialog")


class ExtractAudioDialog(ctk.CTkToplevel):
    """Modal dialog allowing users to extract original or denoised audio from any video."""

    FORMAT_MAP = {
        "MP3 (320 kbps High Quality)": ".mp3",
        "WAV (Lossless 16-bit PCM)": ".wav",
        "FLAC (Lossless Studio)": ".flac",
        "AAC / M4A (320 kbps)": ".m4a",
        "OGG Vorbis (High Quality)": ".ogg",
    }

    def __init__(
        self,
        parent: ctk.CTk,
        default_video_path: Optional[Path] = None,
        denoise_config: Optional[DenoiseConfig] = None,
        on_success: Optional[Callable[[Path], None]] = None
    ) -> None:
        super().__init__(parent)

        self.title("Extract Sound from Video — CNAT NOISERELIEF")
        self.geometry("580x560")
        self.minsize(540, 520)
        self.configure(fg_color=Theme.BG_DARK)

        # Modal configuration
        self.transient(parent)
        self.grab_set()

        self.default_video_path = default_video_path if default_video_path and FFmpegHelper.is_video_file(default_video_path) else None
        self.denoise_config = denoise_config or DenoiseConfig()
        self.on_success = on_success
        self.is_processing = False
        self.last_extracted_path: Optional[Path] = None

        self._center_window(parent)
        self._build_ui()

    def _center_window(self, parent: ctk.CTk) -> None:
        parent.update_idletasks()
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        w, h = 580, 560
        x = max(0, p_x + (p_w - w) // 2)
        y = max(0, p_y + (p_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(
            self,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_MD,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        container.pack(fill="both", expand=True, padx=16, pady=16)
        container.grid_columnconfigure(1, weight=1)

        # Header Title
        title_lbl = ctk.CTkLabel(
            container,
            text="🎵 Extract Sound from Video",
            font=Theme.FONT_TITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        title_lbl.grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 2), sticky="w")

        subtitle_lbl = ctk.CTkLabel(
            container,
            text="Extract original audio tracks or cleaned sound directly from any video container.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        subtitle_lbl.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

        # Divider
        div1 = ctk.CTkFrame(container, fg_color=Theme.CARD_BORDER, height=1)
        div1.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 12))

        # 1. Source Video File
        v_label = ctk.CTkLabel(
            container,
            text="📹 Source Video:",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        v_label.grid(row=3, column=0, padx=(16, 8), pady=6, sticky="w")

        self.video_entry = ctk.CTkEntry(
            container,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            text_color=Theme.TEXT_PRIMARY,
            border_color=Theme.CARD_BORDER,
            height=30
        )
        if self.default_video_path:
            self.video_entry.insert(0, str(self.default_video_path))
        self.video_entry.grid(row=3, column=1, padx=4, pady=6, sticky="ew")

        self.browse_video_btn = ctk.CTkButton(
            container,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=30,
            command=self._on_browse_video
        )
        self.browse_video_btn.grid(row=3, column=2, padx=(4, 16), pady=6)

        # 2. Extraction Mode (Raw vs Cleaned)
        mode_label = ctk.CTkLabel(
            container,
            text="⚙️ Audio Mode:",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        mode_label.grid(row=4, column=0, padx=(16, 8), pady=8, sticky="w")

        self.mode_var = ctk.StringVar(value="raw")
        self.mode_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.mode_frame.grid(row=4, column=1, columnspan=2, padx=4, pady=8, sticky="w")

        self.radio_raw = ctk.CTkRadioButton(
            self.mode_frame,
            text="Original Raw Audio (Fastest, Untouched)",
            variable=self.mode_var,
            value="raw",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY,
            fg_color=Theme.ACCENT_CYAN,
            command=self._update_filename_preview
        )
        self.radio_raw.pack(anchor="w", pady=(0, 4))

        self.radio_clean = ctk.CTkRadioButton(
            self.mode_frame,
            text="Cleaned & Denoised Audio (DSP Noise Suppression)",
            variable=self.mode_var,
            value="clean",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY,
            fg_color=Theme.ACCENT_CLEAN,
            command=self._update_filename_preview
        )
        self.radio_clean.pack(anchor="w")

        # 3. Output Audio Format
        fmt_label = ctk.CTkLabel(
            container,
            text="🎼 Audio Format:",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        fmt_label.grid(row=5, column=0, padx=(16, 8), pady=8, sticky="w")

        self.fmt_menu = ctk.CTkOptionMenu(
            container,
            values=list(self.FORMAT_MAP.keys()),
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            button_color=Theme.ACCENT_CYAN,
            command=lambda _: self._update_filename_preview(),
            height=30
        )
        self.fmt_menu.set("MP3 (320 kbps High Quality)")
        self.fmt_menu.grid(row=5, column=1, padx=4, pady=8, sticky="w")

        # 4. Destination Folder
        dest_label = ctk.CTkLabel(
            container,
            text="📁 Save Folder:",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        dest_label.grid(row=6, column=0, padx=(16, 8), pady=6, sticky="w")

        default_dir = Path.home() / "Desktop" / "Extracted_Audio"
        self.dest_entry = ctk.CTkEntry(
            container,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            text_color=Theme.TEXT_PRIMARY,
            border_color=Theme.CARD_BORDER,
            height=30
        )
        self.dest_entry.insert(0, str(default_dir))
        self.dest_entry.grid(row=6, column=1, padx=4, pady=6, sticky="ew")

        self.browse_dest_btn = ctk.CTkButton(
            container,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=30,
            command=self._on_browse_dest
        )
        self.browse_dest_btn.grid(row=6, column=2, padx=(4, 16), pady=6)

        # 5. Output Filename Preview
        file_label = ctk.CTkLabel(
            container,
            text="📄 File Name:",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        file_label.grid(row=7, column=0, padx=(16, 8), pady=6, sticky="w")

        self.filename_entry = ctk.CTkEntry(
            container,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            text_color=Theme.TEXT_PRIMARY,
            border_color=Theme.CARD_BORDER,
            height=30
        )
        self.filename_entry.grid(row=7, column=1, columnspan=2, padx=(4, 16), pady=6, sticky="ew")
        self._update_filename_preview()

        # Divider
        div2 = ctk.CTkFrame(container, fg_color=Theme.CARD_BORDER, height=1)
        div2.grid(row=8, column=0, columnspan=3, sticky="ew", padx=16, pady=(10, 8))

        # Progress Bar & Status
        self.prog_bar = ctk.CTkProgressBar(
            container,
            progress_color=Theme.ACCENT_CLEAN,
            height=10
        )
        self.prog_bar.set(0.0)
        self.prog_bar.grid(row=9, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 2))

        self.status_label = ctk.CTkLabel(
            container,
            text="Ready to extract audio.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.status_label.grid(row=10, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 10))

        # Bottom Buttons (Extract, Open Folder, Close)
        self.action_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.action_frame.grid(row=11, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 14))
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.open_folder_btn = ctk.CTkButton(
            self.action_frame,
            text="📂 Open Folder",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            width=120,
            height=34,
            command=self._on_open_folder,
            state="disabled"
        )
        self.open_folder_btn.pack(side="left")

        self.close_btn = ctk.CTkButton(
            self.action_frame,
            text="Close",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            width=90,
            height=34,
            command=self.destroy
        )
        self.close_btn.pack(side="right", padx=(8, 0))

        self.extract_btn = ctk.CTkButton(
            self.action_frame,
            text="⚡ EXTRACT AUDIO",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CLEAN,
            hover_color=Theme.ACCENT_CLEAN_HOVER,
            text_color="#FFFFFF",
            width=180,
            height=34,
            command=self._start_extraction
        )
        self.extract_btn.pack(side="right")

    def _on_browse_video(self) -> None:
        file_path_str = filedialog.askopenfilename(
            title="Select Video File to Extract Audio",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v *.ts"),
                ("All Files", "*.*")
            ]
        )
        if file_path_str:
            self.video_entry.delete(0, "end")
            self.video_entry.insert(0, file_path_str)
            self._update_filename_preview()

            # Check if video has audio stream
            p = Path(file_path_str)
            if not FFmpegHelper.has_audio_stream(p):
                self.status_label.configure(
                    text="⚠️ Warning: This video file has no audio stream (it is silent).",
                    text_color=Theme.ACCENT_AMBER
                )
            else:
                self.status_label.configure(
                    text=f"Loaded video: {p.name} (Audio stream detected)",
                    text_color=Theme.TEXT_SECONDARY
                )

    def _on_browse_dest(self) -> None:
        sel = filedialog.askdirectory(title="Select Destination Directory")
        if sel:
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, sel)

    def _update_filename_preview(self) -> None:
        v_str = self.video_entry.get().strip()
        stem = Path(v_str).stem if v_str else "video_audio"
        ext = self.FORMAT_MAP.get(self.fmt_menu.get(), ".mp3")
        mode = self.mode_var.get()

        tag = "_cleaned" if mode == "clean" else "_extracted"
        suggested = f"{stem}{tag}{ext}"

        self.filename_entry.delete(0, "end")
        self.filename_entry.insert(0, suggested)

    def _start_extraction(self) -> None:
        if self.is_processing:
            return

        v_str = self.video_entry.get().strip()
        if not v_str or not Path(v_str).exists():
            self.status_label.configure(text="⚠️ Please select a valid source video file.", text_color=Theme.ACCENT_DIRTY)
            return

        video_path = Path(v_str)

        # Validate that the video contains an audio track
        if not FFmpegHelper.has_audio_stream(video_path):
            self.status_label.configure(
                text=f"❌ '{video_path.name}' contains no audio track to extract (video is silent).",
                text_color=Theme.ACCENT_DIRTY
            )
            return

        dest_dir_str = self.dest_entry.get().strip()
        dest_dir = Path(dest_dir_str)
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = self.filename_entry.get().strip()
        if not filename:
            self._update_filename_preview()
            filename = self.filename_entry.get().strip()

        target_audio_path = dest_dir / filename
        is_clean = (self.mode_var.get() == "clean")

        self.is_processing = True
        self.extract_btn.configure(state="disabled", text="Extracting...")
        self.browse_video_btn.configure(state="disabled")
        self.browse_dest_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.prog_bar.set(0.1)

        def _worker():
            try:
                def _prog_cb(pct: float, msg: str):
                    self.after(0, lambda p=pct, m=msg: self._update_ui_progress(p, m))

                _prog_cb(10.0, "Starting audio extraction...")
                out_file = VideoEngine.extract_sound(
                    video_path=video_path,
                    output_audio_path=target_audio_path,
                    denoise=is_clean,
                    config=self.denoise_config,
                    sample_rate=48000,
                    progress_callback=_prog_cb
                )

                self.last_extracted_path = out_file
                self.after(0, lambda f=out_file: self._on_extraction_completed(f))
            except Exception as ex:
                err_msg = str(ex) if str(ex) else f"Extraction failed: {type(ex).__name__}"
                logger.error(f"Failed to extract sound from video: {err_msg}")
                self.after(0, lambda msg=err_msg: self._on_extraction_failed(msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_ui_progress(self, percent: float, message: str) -> None:
        self.prog_bar.set(min(max(percent / 100.0, 0.0), 1.0))
        self.status_label.configure(
            text=f"[{int(percent)}%] {message}",
            text_color=Theme.TEXT_SECONDARY
        )

    def _on_extraction_completed(self, out_path: Path) -> None:
        self.is_processing = False
        self.prog_bar.set(1.0)
        self.extract_btn.configure(state="normal", text="⚡ EXTRACT AUDIO")
        self.browse_video_btn.configure(state="normal")
        self.browse_dest_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self.status_label.configure(
            text=f"✅ Extracted successfully: {out_path.name}",
            text_color=Theme.ACCENT_CLEAN
        )
        if self.on_success:
            self.on_success(out_path)

    def _on_extraction_failed(self, error_msg: str) -> None:
        self.is_processing = False
        self.prog_bar.set(0.0)
        self.extract_btn.configure(state="normal", text="⚡ EXTRACT AUDIO")
        self.browse_video_btn.configure(state="normal")
        self.browse_dest_btn.configure(state="normal")
        self.status_label.configure(
            text=f"❌ Extraction error: {error_msg}",
            text_color=Theme.ACCENT_DIRTY
        )

    def _on_open_folder(self) -> None:
        dest_dir = Path(self.dest_entry.get().strip())
        if dest_dir.exists():
            if sys.platform == "win32":
                os.startfile(str(dest_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(dest_dir)])
            else:
                subprocess.Popen(["xdg-open", str(dest_dir)])

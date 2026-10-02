"""Vocal Isolation and Instrumental/Karaoke Separation Dialog for CNAT NOISERELIEF."""
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, Tuple
from tkinter import filedialog
import customtkinter as ctk

from src.gui.theme import Theme
from src.utils.ffmpeg_helper import FFmpegHelper
from src.utils.audio_io import AudioIO
from src.core.vocal_extractor import VocalExtractor, VocalExtractionConfig
from src.utils.logger import get_logger

logger = get_logger("VocalExtractorDialog")


class VocalExtractorDialog(ctk.CTkToplevel):
    """Modern modal dialog for extracting clean vocals (acapella) and instrumentals."""

    def __init__(
        self,
        parent: ctk.CTk,
        default_media_path: Optional[Path] = None,
        on_success: Optional[Callable[[list[Path]], None]] = None
    ) -> None:
        super().__init__(parent)

        self.title("🎤 Vocal & Music Separator (Acapella / Karaoke) — CNAT NOISERELIEF")
        self.geometry("620x700")
        self.minsize(580, 640)
        self.configure(fg_color=Theme.BG_DARK)

        # Modal configuration
        self.transient(parent)
        self.grab_set()

        self.default_media_path = default_media_path
        self.on_success = on_success
        self.is_processing = False
        self.media_duration: float = 0.0

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

        w, h = 620, 700
        x = max(0, p_x + (p_w - w) // 2)
        y = max(0, p_y + (p_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 1. Header Card
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
            text="🎤 Studio Vocal & Music Separator",
            font=Theme.FONT_SUBHEADING,
            text_color=Theme.TEXT_PRIMARY
        )
        self.header_title.pack(anchor="w", padx=14, pady=(10, 2))

        self.header_desc = ctk.CTkLabel(
            self.header_card,
            text="Isolate lead vocals (Acapella / Speech) or remove vocals to create clean Instrumental tracks.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.header_desc.pack(anchor="w", padx=14, pady=(0, 10))

        # 2. Media Source Card
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
            text="📁 Source Audio or Video File",
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
            text="Duration: 00:00:00 | Channels: Unknown",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED
        )
        self.meta_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 10))

        # 3. Target Extraction Mode
        self.mode_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.mode_card.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self.mode_label = ctk.CTkLabel(
            self.mode_card,
            text="🎯 Separation Target",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_PRIMARY
        )
        self.mode_label.pack(anchor="w", padx=14, pady=(10, 6))

        self.target_mode_var = ctk.StringVar(value="vocals_only")

        self.radio_vocals = ctk.CTkRadioButton(
            self.mode_card,
            text="🎤 Extract Vocals Only (Acapella / Isolated Voice Track)",
            variable=self.target_mode_var,
            value="vocals_only",
            font=Theme.FONT_BODY
        )
        self.radio_vocals.pack(anchor="w", padx=14, pady=(0, 6))

        self.radio_both = ctk.CTkRadioButton(
            self.mode_card,
            text="✨ Extract Both (Separate into Vocals.wav + Instrumental.wav)",
            variable=self.target_mode_var,
            value="both",
            font=Theme.FONT_BODY
        )
        self.radio_both.pack(anchor="w", padx=14, pady=(0, 6))

        self.radio_inst = ctk.CTkRadioButton(
            self.mode_card,
            text="🎹 Extract Instrumental Only (Karaoke / Music without Vocals)",
            variable=self.target_mode_var,
            value="inst_only",
            font=Theme.FONT_BODY
        )
        self.radio_inst.pack(anchor="w", padx=14, pady=(0, 10))

        # 4. DSP Parameters & Tuning
        self.params_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.params_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self.params_card.grid_columnconfigure(1, weight=1)

        self.params_title = ctk.CTkLabel(
            self.params_card,
            text="🎛️ Vocal Isolation Parameters",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_PRIMARY
        )
        self.params_title.grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 8))

        # Sensitivity Slider
        self.sens_label = ctk.CTkLabel(self.params_card, text="Vocal Aggression:", font=Theme.FONT_BODY)
        self.sens_label.grid(row=1, column=0, sticky="w", padx=(14, 8), pady=(0, 8))

        self.sens_slider = ctk.CTkSlider(
            self.params_card,
            from_=0.50,
            to=1.0,
            number_of_steps=50,
            progress_color=Theme.ACCENT_CYAN,
            command=self._on_sens_change
        )
        self.sens_slider.set(0.85)
        self.sens_slider.grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))

        self.sens_val_lbl = ctk.CTkLabel(self.params_card, text="85%", font=Theme.FONT_SMALL, width=40)
        self.sens_val_lbl.grid(row=1, column=2, padx=(0, 14), pady=(0, 8))

        # Checkboxes
        self.formant_boost_var = ctk.BooleanVar(value=True)
        self.formant_chk = ctk.CTkCheckBox(
            self.params_card,
            text="✨ Boost Voice Presence & Intelligibility (2.5 - 4.0 kHz)",
            variable=self.formant_boost_var,
            font=Theme.FONT_BODY
        )
        self.formant_chk.grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 6))

        self.filter_bass_var = ctk.BooleanVar(value=True)
        self.bass_chk = ctk.CTkCheckBox(
            self.params_card,
            text="🥁 Suppress Sub-Bass, Kick Drums (< 100 Hz) & Cymbals (> 8.5 kHz)",
            variable=self.filter_bass_var,
            font=Theme.FONT_BODY
        )
        self.bass_chk.grid(row=3, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))

        # 5. Output Format & Directory
        self.dest_card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=Theme.CARD_BG,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_width=1,
            border_color=Theme.CARD_BORDER
        )
        self.dest_card.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        self.dest_card.grid_columnconfigure(0, weight=1)

        self.dest_header_frame = ctk.CTkFrame(self.dest_card, fg_color="transparent")
        self.dest_header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 4))

        self.dest_label = ctk.CTkLabel(
            self.dest_header_frame,
            text="📁 Output Directory & Format",
            font=Theme.FONT_BODY_BOLD,
            text_color=Theme.TEXT_PRIMARY
        )
        self.dest_label.pack(side="left")

        self.format_menu = ctk.CTkOptionMenu(
            self.dest_header_frame,
            values=["WAV (Lossless PCM)", "MP3 (320 kbps)", "FLAC (Lossless)", "AAC (High Quality)", "OGG Vorbis"],
            font=Theme.FONT_SMALL,
            width=160,
            height=26
        )
        self.format_menu.set("WAV (Lossless PCM)")
        self.format_menu.pack(side="right")

        default_out = Path.home() / "Music" / "CNAT_NoiseRelief_Vocals"
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

        # 6. Progress & Buttons
        self.progress_bar = ctk.CTkProgressBar(
            self.scroll_frame,
            height=8,
            progress_color=Theme.ACCENT_CYAN
        )
        self.progress_bar.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        self.progress_bar.set(0.0)

        self.status_label = ctk.CTkLabel(
            self.scroll_frame,
            text="Ready to extract vocals.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.status_label.grid(row=6, column=0, sticky="w", pady=(0, 10))

        self.btn_action_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.btn_action_frame.grid(row=7, column=0, sticky="ew")

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
            text="🎤 Extract Vocals Now",
            fg_color=Theme.ACCENT_CYAN,
            text_color="#000000",
            font=Theme.FONT_BODY_BOLD,
            hover_color="#0891B2",
            command=self._on_start_extraction
        )
        self.start_btn.pack(side="right")

    def _on_sens_change(self, val: float) -> None:
        self.sens_val_lbl.configure(text=f"{int(val * 100)}%")

    def _on_browse_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Audio or Video Track",
            filetypes=[
                ("All Supported Media", "*.wav;*.mp3;*.flac;*.aac;*.m4a;*.ogg;*.mp4;*.mkv;*.mov;*.avi"),
                ("Audio Files", "*.wav;*.mp3;*.flac;*.aac;*.m4a;*.ogg"),
                ("Video Files", "*.mp4;*.mkv;*.mov;*.avi"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self._set_selected_media(Path(file_path))

    def _set_selected_media(self, path: Path) -> None:
        self.default_media_path = path
        self.file_path_var.set(str(path))
        is_video = FFmpegHelper.is_video_file(path)

        try:
            if is_video:
                self.media_duration = FFmpegHelper.get_media_duration(path)
                m_type = f"Video ({path.suffix.upper()})"
            else:
                arr, sr = AudioIO.load_audio(path)
                self.media_duration = arr.shape[-1] / float(sr)
                m_type = f"Audio ({path.suffix.upper()}) | {sr/1000.0:.1f}kHz | {'Stereo' if arr.ndim > 1 else 'Mono'}"

            s = max(0.0, self.media_duration)
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = s % 60
            self.meta_label.configure(
                text=f"Duration: {h:02d}:{m:02d}:{sec:04.1f} ({self.media_duration:.1f}s) | Type: {m_type}"
            )
        except Exception as ex:
            self.meta_label.configure(text=f"Error reading media: {ex}")

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

    def _on_start_extraction(self) -> None:
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

        out_dir = Path(self.dest_path_var.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)

        # Format extension
        fmt_choice = self.format_menu.get()
        if "MP3" in fmt_choice:
            ext = ".mp3"
        elif "FLAC" in fmt_choice:
            ext = ".flac"
        elif "AAC" in fmt_choice:
            ext = ".m4a"
        elif "OGG" in fmt_choice:
            ext = ".ogg"
        else:
            ext = ".wav"

        stem = in_path.stem
        target_mode = self.target_mode_var.get()

        vocal_out = out_dir / f"{stem}_vocals{ext}" if target_mode in {"vocals_only", "both"} else None
        inst_out = out_dir / f"{stem}_instrumental{ext}" if target_mode in {"inst_only", "both"} else None

        config = VocalExtractionConfig(
            vocal_sensitivity=float(self.sens_slider.get()),
            enhance_speech_formants=self.formant_boost_var.get(),
            remove_drums_bass=self.filter_bass_var.get(),
            vocal_low_cutoff_hz=100.0 if self.filter_bass_var.get() else 40.0,
            vocal_high_cutoff_hz=8500.0 if self.filter_bass_var.get() else 18000.0
        )

        self.is_processing = True
        self.start_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress_bar.set(0.1)

        def _worker():
            try:
                def _prog(pct: float, msg: str):
                    self.after(0, lambda: self._update_progress(pct, msg))

                v_res, i_res = VocalExtractor.extract_vocal_file(
                    input_media_path=in_path,
                    output_vocal_path=vocal_out,
                    output_instrumental_path=inst_out,
                    config=config,
                    progress_callback=_prog
                )

                created = [p for p in (v_res, i_res) if p is not None]
                self.after(0, lambda: self._on_complete(created))
            except Exception as ex:
                logger.error(f"Vocal extraction failed: {ex}")
                self.after(0, lambda: self._on_error(str(ex)))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, pct: float, msg: str) -> None:
        self.progress_bar.set(pct / 100.0)
        self.status_label.configure(text=msg, text_color=Theme.TEXT_SECONDARY)

    def _on_complete(self, files: list[Path]) -> None:
        self.is_processing = False
        self.start_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self.progress_bar.set(1.0)
        names = ", ".join([f.name for f in files])
        self.status_label.configure(
            text=f"✅ Done! Saved: {names}",
            text_color=Theme.ACCENT_GREEN
        )
        if self.on_success:
            self.on_success(files)

    def _on_error(self, err_msg: str) -> None:
        self.is_processing = False
        self.start_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.progress_bar.set(0.0)
        self.status_label.configure(
            text=f"❌ Error: {err_msg}",
            text_color=Theme.ACCENT_RED
        )

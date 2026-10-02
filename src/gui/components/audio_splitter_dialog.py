"""Audio Splitter & Silence-Based Take Cutter Dialog for CNAT NOISERELIEF."""
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from tkinter import filedialog
import customtkinter as ctk

from src.gui.theme import Theme
from src.utils.audio_io import AudioIO
from src.core.audio_engine import AudioDenoiseEngine, DenoiseConfig
from src.utils.logger import get_logger

logger = get_logger("AudioSplitterDialog")


class AudioSplitterDialog(ctk.CTkToplevel):
    """Modern modal dialog for audio splitting, silence pause detection, and range trimming."""

    def __init__(
        self,
        parent: ctk.CTk,
        default_audio_path: Optional[Path] = None,
        denoise_config: Optional[DenoiseConfig] = None,
        on_success: Optional[Callable[[list[Path]], None]] = None
    ) -> None:
        super().__init__(parent)

        self.title("✂️ Audio Track Splitter & Cutter — CNAT NOISERELIEF")
        self.geometry("620x640")
        self.minsize(580, 600)
        self.configure(fg_color=Theme.BG_DARK)

        # Modal configuration
        self.transient(parent)
        self.grab_set()

        self.default_audio_path = default_audio_path
        self.denoise_config = denoise_config or DenoiseConfig()
        self.on_success = on_success
        self.is_processing = False
        self.audio_duration: float = 0.0

        self._center_window(parent)
        self._build_ui()

        if self.default_audio_path and self.default_audio_path.exists():
            self._set_selected_audio(self.default_audio_path)

    def _center_window(self, parent: ctk.CTk) -> None:
        parent.update_idletasks()
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        w, h = 620, 640
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

        # Title Banner
        title_lbl = ctk.CTkLabel(
            container,
            text="✂️  Audio Splitter & Silence Detector",
            font=Theme.FONT_TITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        title_lbl.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 2))

        subtitle_lbl = ctk.CTkLabel(
            container,
            text="Split audio by duration, equal parts, custom cut range, or automatic pause/silence detection",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        subtitle_lbl.grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 10))

        # 1. Audio File Selection
        a_label = ctk.CTkLabel(container, text="Source Audio:", font=Theme.FONT_BODY, text_color=Theme.TEXT_PRIMARY)
        a_label.grid(row=2, column=0, sticky="w", padx=16, pady=4)

        self.audio_entry = ctk.CTkEntry(
            container,
            placeholder_text="Select an audio file (.wav, .mp3, .flac, .aac, .m4a, .ogg)...",
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            border_color=Theme.CARD_BORDER,
            height=32
        )
        self.audio_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        self.browse_btn = ctk.CTkButton(
            container,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=32,
            command=self._on_browse_audio
        )
        self.browse_btn.grid(row=2, column=2, padx=(0, 16), pady=4)

        # Info / Duration Label
        self.info_label = ctk.CTkLabel(
            container,
            text="Duration: --:-- | Channels: -- | Sample Rate: -- kHz",
            font=Theme.FONT_SMALL,
            text_color=Theme.ACCENT_CYAN
        )
        self.info_label.grid(row=3, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 6))

        # 2. Split Strategy Frame
        mode_frame = ctk.CTkFrame(container, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        mode_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=16, pady=4)
        mode_frame.grid_columnconfigure(0, weight=1)

        mode_hdr = ctk.CTkLabel(mode_frame, text="Split Strategy:", font=Theme.FONT_SUBTITLE, text_color=Theme.TEXT_PRIMARY)
        mode_hdr.pack(anchor="w", padx=12, pady=(6, 2))

        self.split_mode_var = ctk.StringVar(value="duration")

        # Option A: By Fixed Duration
        self.rad_dur = ctk.CTkRadioButton(
            mode_frame,
            text="Fixed Duration Clips (e.g., 30s Ringtones / Samples)",
            variable=self.split_mode_var,
            value="duration",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_dur.pack(anchor="w", padx=12, pady=2)

        self.dur_box = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.dur_box.pack(anchor="w", padx=36, pady=(0, 4))
        ctk.CTkLabel(self.dur_box, text="Length:", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self.duration_spinbox = ctk.CTkOptionMenu(
            self.dur_box,
            values=["15 Seconds", "30 Seconds", "45 Seconds", "60 Seconds (1 Min)", "120 Seconds (2 Mins)", "300 Seconds (5 Mins)"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG,
            button_color=Theme.ACCENT_CYAN,
            width=180,
            height=26
        )
        self.duration_spinbox.set("30 Seconds")
        self.duration_spinbox.pack(side="left")

        # Option B: Auto Split on Silence / Pauses
        self.rad_silence = ctk.CTkRadioButton(
            mode_frame,
            text="Auto-Detect Silence / Pauses (Split into Speech Takes / Sentences)",
            variable=self.split_mode_var,
            value="silence",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_silence.pack(anchor="w", padx=12, pady=2)

        self.silence_box = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.silence_box.pack(anchor="w", padx=36, pady=(0, 4))
        ctk.CTkLabel(self.silence_box, text="Min Pause:", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.silence_dur_menu = ctk.CTkOptionMenu(
            self.silence_box,
            values=["0.5s Pause", "0.8s Pause", "1.0s Pause", "1.5s Pause", "2.0s Pause"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG,
            button_color=Theme.ACCENT_CYAN,
            width=120,
            height=26
        )
        self.silence_dur_menu.set("0.8s Pause")
        self.silence_dur_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(self.silence_box, text="Threshold:", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.silence_thresh_menu = ctk.CTkOptionMenu(
            self.silence_box,
            values=["-30 dB (Noisy)", "-38 dB (Normal)", "-45 dB (Quiet)", "-50 dB (Studio)"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG,
            button_color=Theme.ACCENT_CYAN,
            width=140,
            height=26
        )
        self.silence_thresh_menu.set("-38 dB (Normal)")
        self.silence_thresh_menu.pack(side="left")

        # Option C: Equal Parts
        self.rad_parts = ctk.CTkRadioButton(
            mode_frame,
            text="Equal Parts Division (e.g., Part 1, Part 2...)",
            variable=self.split_mode_var,
            value="parts",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_parts.pack(anchor="w", padx=12, pady=2)

        self.parts_box = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.parts_box.pack(anchor="w", padx=36, pady=(0, 4))
        ctk.CTkLabel(self.parts_box, text="Parts:", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self.parts_menu = ctk.CTkOptionMenu(
            self.parts_box,
            values=["2 Parts", "3 Parts", "4 Parts", "5 Parts", "8 Parts", "10 Parts"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG,
            button_color=Theme.ACCENT_CYAN,
            width=140,
            height=26
        )
        self.parts_menu.set("2 Parts")
        self.parts_menu.pack(side="left")

        # Option D: Custom Range Trim
        self.rad_trim = ctk.CTkRadioButton(
            mode_frame,
            text="Custom Start / End Cut Range",
            variable=self.split_mode_var,
            value="trim",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_trim.pack(anchor="w", padx=12, pady=2)

        self.trim_box = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.trim_box.pack(anchor="w", padx=36, pady=(0, 6))
        ctk.CTkLabel(self.trim_box, text="Start (s):", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.trim_start_entry = ctk.CTkEntry(self.trim_box, width=60, height=24, font=Theme.FONT_SMALL)
        self.trim_start_entry.insert(0, "0.0")
        self.trim_start_entry.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(self.trim_box, text="End (s):", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.trim_end_entry = ctk.CTkEntry(self.trim_box, width=60, height=24, font=Theme.FONT_SMALL)
        self.trim_end_entry.insert(0, "60.0")
        self.trim_end_entry.pack(side="left")

        # 3. Format & Options Row
        fmt_row = ctk.CTkFrame(container, fg_color="transparent")
        fmt_row.grid(row=5, column=0, columnspan=3, sticky="ew", padx=16, pady=4)

        ctk.CTkLabel(fmt_row, text="Export Format:", font=Theme.FONT_BODY, text_color=Theme.TEXT_PRIMARY).pack(side="left", padx=(0, 6))
        self.fmt_menu = ctk.CTkOptionMenu(
            fmt_row,
            values=["WAV (Lossless PCM)", "MP3 (320 kbps)", "FLAC (Studio)", "AAC (High Quality)", "OGG Vorbis"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            button_color=Theme.ACCENT_CYAN,
            width=170,
            height=28
        )
        self.fmt_menu.set("WAV (Lossless PCM)")
        self.fmt_menu.pack(side="left", padx=(0, 14))

        self.denoise_chk = ctk.CTkCheckBox(
            fmt_row,
            text="Apply Noise Reduction to Segments",
            font=Theme.FONT_SMALL,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.denoise_chk.pack(side="left")

        # 4. Output Directory
        out_lbl = ctk.CTkLabel(container, text="Output Folder:", font=Theme.FONT_BODY, text_color=Theme.TEXT_PRIMARY)
        out_lbl.grid(row=6, column=0, sticky="w", padx=16, pady=4)

        self.default_out_dir = Path.home() / "Desktop" / "Split_Audio_Clips"
        self.out_entry = ctk.CTkEntry(
            container,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            border_color=Theme.CARD_BORDER,
            height=30
        )
        self.out_entry.insert(0, str(self.default_out_dir))
        self.out_entry.grid(row=6, column=1, sticky="ew", padx=6, pady=4)

        self.out_btn = ctk.CTkButton(
            container,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=30,
            command=self._on_browse_output
        )
        self.out_btn.grid(row=6, column=2, padx=(0, 16), pady=4)

        # 5. Progress Bar & Status
        self.prog_bar = ctk.CTkProgressBar(container, progress_color=Theme.ACCENT_CLEAN, height=10)
        self.prog_bar.set(0.0)
        self.prog_bar.grid(row=7, column=0, columnspan=3, sticky="ew", padx=16, pady=(6, 2))

        self.status_lbl = ctk.CTkLabel(container, text="Ready to split audio.", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY)
        self.status_lbl.grid(row=8, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 6))

        # 6. Action Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.grid(row=9, column=0, columnspan=3, sticky="ew", padx=16, pady=(2, 10))

        self.open_dir_btn = ctk.CTkButton(
            btn_box,
            text="📂 Open Output Folder",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            width=160,
            height=34,
            command=self._open_output_dir
        )
        self.open_dir_btn.pack(side="left")

        self.split_btn = ctk.CTkButton(
            btn_box,
            text="✂️  START AUDIO SPLIT",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CLEAN,
            hover_color=Theme.ACCENT_CLEAN_HOVER,
            text_color="#FFFFFF",
            width=190,
            height=34,
            command=self._start_split_thread
        )
        self.split_btn.pack(side="right")

    def _on_browse_audio(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Audio File to Split",
            filetypes=[
                ("Audio Files", "*.wav *.mp3 *.flac *.aac *.m4a *.ogg"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self._set_selected_audio(Path(file_path))

    def _set_selected_audio(self, path: Path) -> None:
        self.audio_entry.delete(0, "end")
        self.audio_entry.insert(0, str(path))
        try:
            meta = AudioIO.get_audio_metadata(path)
            dur = meta["duration"]
            self.audio_duration = dur
            mins = int(dur // 60)
            secs = int(dur % 60)
            ch_str = "Stereo" if meta["channels"] > 1 else "Mono"
            sr_khz = meta["sample_rate"] / 1000.0
            self.info_label.configure(text=f"Duration: {mins:02d}:{secs:02d} ({dur:.1f}s) | {ch_str} | {sr_khz:.1f} kHz")
            self.trim_end_entry.delete(0, "end")
            self.trim_end_entry.insert(0, f"{dur:.1f}")
        except Exception:
            self.info_label.configure(text="Audio loaded.")

    def _on_browse_output(self) -> None:
        sel = filedialog.askdirectory(title="Select Destination Folder")
        if sel:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, str(sel))

    def _get_target_format(self) -> str:
        val = self.fmt_menu.get().lower()
        if "mp3" in val:
            return "mp3"
        if "flac" in val:
            return "flac"
        if "aac" in val:
            return "m4a"
        if "ogg" in val:
            return "ogg"
        return "wav"

    def _start_split_thread(self) -> None:
        if self.is_processing:
            return

        a_text = self.audio_entry.get().strip()
        if not a_text or not Path(a_text).exists():
            self.status_lbl.configure(text="[Error] Please select a valid audio file first.", text_color=Theme.ACCENT_DIRTY)
            return

        out_text = self.out_entry.get().strip() or str(self.default_out_dir)
        a_path = Path(a_text)
        out_dir = Path(out_text)
        out_dir.mkdir(parents=True, exist_ok=True)

        mode = self.split_mode_var.get()
        denoise = bool(self.denoise_chk.get())
        fmt = self._get_target_format()

        self.is_processing = True
        self.split_btn.configure(state="disabled", text="Splitting Audio...")
        self.browse_btn.configure(state="disabled")

        def _worker():
            try:
                def _prog(pct: float, msg: str):
                    self.after(0, lambda: self._update_ui_progress(pct, msg))

                if mode == "duration":
                    dur_val_text = self.duration_spinbox.get()
                    sec = float(dur_val_text.split()[0])
                    results = AudioDenoiseEngine.split_audio_by_duration(
                        audio_path=a_path,
                        segment_duration_sec=sec,
                        output_dir=out_dir,
                        output_format=fmt,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )
                elif mode == "silence":
                    dur_text = self.silence_dur_menu.get()
                    silence_sec = float(dur_text.replace("s Pause", "").strip())
                    thresh_text = self.silence_thresh_menu.get()
                    db_val = float(thresh_text.split()[0])

                    results = AudioDenoiseEngine.split_audio_by_silence(
                        audio_path=a_path,
                        output_dir=out_dir,
                        min_silence_len_sec=silence_sec,
                        silence_threshold_db=db_val,
                        output_format=fmt,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )
                elif mode == "parts":
                    part_text = self.parts_menu.get()
                    num = int(part_text.split()[0])
                    results = AudioDenoiseEngine.split_audio_by_parts(
                        audio_path=a_path,
                        num_parts=num,
                        output_dir=out_dir,
                        output_format=fmt,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )
                else:
                    # Custom Trim
                    s_sec = float(self.trim_start_entry.get().strip())
                    e_sec = float(self.trim_end_entry.get().strip())
                    out_clip = out_dir / f"{a_path.stem}_trimmed.{fmt}"
                    results = [AudioDenoiseEngine.trim_audio_range(
                        audio_path=a_path,
                        start_sec=s_sec,
                        end_sec=e_sec,
                        output_path=out_clip,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )]

                self.after(0, lambda: self._on_finish_success(results))
            except Exception as ex:
                logger.error(f"Audio splitting error: {ex}")
                self.after(0, lambda: self._on_finish_error(str(ex)))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_ui_progress(self, percent: float, msg: str) -> None:
        self.prog_bar.set(min(max(percent / 100.0, 0.0), 1.0))
        self.status_lbl.configure(text=f"[{int(percent)}%] {msg}", text_color=Theme.TEXT_SECONDARY)

    def _on_finish_success(self, created_files: list[Path]) -> None:
        self.is_processing = False
        self.split_btn.configure(state="normal", text="✂️  START AUDIO SPLIT")
        self.browse_btn.configure(state="normal")
        self.prog_bar.set(1.0)
        self.status_lbl.configure(
            text=f"✅ Done! Successfully generated {len(created_files)} audio segments.",
            text_color=Theme.ACCENT_CLEAN
        )
        if self.on_success:
            self.on_success(created_files)

    def _on_finish_error(self, err_msg: str) -> None:
        self.is_processing = False
        self.split_btn.configure(state="normal", text="✂️  START AUDIO SPLIT")
        self.browse_btn.configure(state="normal")
        self.prog_bar.set(0.0)
        self.status_lbl.configure(text=f"❌ Error: {err_msg}", text_color=Theme.ACCENT_DIRTY)

    def _open_output_dir(self) -> None:
        out_text = self.out_entry.get().strip() or str(self.default_out_dir)
        p = Path(out_text)
        p.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as ex:
            logger.warning(f"Could not open directory: {ex}")

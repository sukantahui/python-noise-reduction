"""Video Splitter & Trimmer Dialog for CNAT NOISERELIEF."""
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
from src.core.video_engine import VideoEngine
from src.core.audio_engine import DenoiseConfig
from src.utils.logger import get_logger

logger = get_logger("VideoSplitterDialog")


class VideoSplitterDialog(ctk.CTkToplevel):
    """Modern modal dialog providing lossless video splitting, cutting, and trimming."""

    def __init__(
        self,
        parent: ctk.CTk,
        default_video_path: Optional[Path] = None,
        denoise_config: Optional[DenoiseConfig] = None,
        on_success: Optional[Callable[[list[Path]], None]] = None
    ) -> None:
        super().__init__(parent)

        self.title("✂️ Video Splitter & Cutter — CNAT NOISERELIEF")
        self.geometry("620x620")
        self.minsize(580, 580)
        self.configure(fg_color=Theme.BG_DARK)

        # Modal configuration
        self.transient(parent)
        self.grab_set()

        self.default_video_path = default_video_path if default_video_path and FFmpegHelper.is_video_file(default_video_path) else None
        self.denoise_config = denoise_config or DenoiseConfig()
        self.on_success = on_success
        self.is_processing = False
        self.video_duration: float = 0.0

        self._center_window(parent)
        self._build_ui()

        if self.default_video_path:
            self._set_selected_video(self.default_video_path)

    def _center_window(self, parent: ctk.CTk) -> None:
        parent.update_idletasks()
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        w, h = 620, 620
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
            text="✂️  Video Splitter & Trimmer",
            font=Theme.FONT_TITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        title_lbl.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 2))

        subtitle_lbl = ctk.CTkLabel(
            container,
            text="Split video into equal clips (Shorts/Reels) or trim custom ranges with zero quality loss",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        subtitle_lbl.grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 12))

        # 1. Video File Selection
        v_label = ctk.CTkLabel(container, text="Source Video:", font=Theme.FONT_BODY, text_color=Theme.TEXT_PRIMARY)
        v_label.grid(row=2, column=0, sticky="w", padx=16, pady=4)

        self.video_entry = ctk.CTkEntry(
            container,
            placeholder_text="Select or drop a video file (.mp4, .mkv, .mov, .avi)...",
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            border_color=Theme.CARD_BORDER,
            height=32
        )
        self.video_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        self.browse_btn = ctk.CTkButton(
            container,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=32,
            command=self._on_browse_video
        )
        self.browse_btn.grid(row=2, column=2, padx=(0, 16), pady=4)

        # Video Info / Duration Label
        self.info_label = ctk.CTkLabel(
            container,
            text="Duration: --:-- | Codec: Stream Copy Ready",
            font=Theme.FONT_SMALL,
            text_color=Theme.ACCENT_CYAN
        )
        self.info_label.grid(row=3, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 8))

        # 2. Split Mode Radio Buttons
        mode_frame = ctk.CTkFrame(container, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        mode_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=16, pady=6)
        mode_frame.grid_columnconfigure(0, weight=1)

        mode_hdr = ctk.CTkLabel(mode_frame, text="Split Strategy:", font=Theme.FONT_SUBTITLE, text_color=Theme.TEXT_PRIMARY)
        mode_hdr.pack(anchor="w", padx=12, pady=(8, 4))

        self.split_mode_var = ctk.StringVar(value="duration")

        # Option A: By Fixed Duration (e.g. 30s for Shorts / WhatsApp)
        self.rad_dur = ctk.CTkRadioButton(
            mode_frame,
            text="Split into Fixed Duration Clips (e.g. 30s Shorts/Reels/WhatsApp)",
            variable=self.split_mode_var,
            value="duration",
            command=self._on_mode_toggled,
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_dur.pack(anchor="w", padx=12, pady=4)

        self.dur_input_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.dur_input_frame.pack(anchor="w", padx=36, pady=(0, 6))

        dur_lbl = ctk.CTkLabel(self.dur_input_frame, text="Segment Length (Seconds):", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY)
        dur_lbl.pack(side="left", padx=(0, 8))

        self.duration_spinbox = ctk.CTkOptionMenu(
            self.dur_input_frame,
            values=["15 Seconds (Stories)", "30 Seconds (WhatsApp/Reels)", "60 Seconds (Shorts)", "120 Seconds (2 Mins)", "300 Seconds (5 Mins)", "600 Seconds (10 Mins)"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG,
            button_color=Theme.ACCENT_CYAN,
            width=220,
            height=28
        )
        self.duration_spinbox.set("30 Seconds (WhatsApp/Reels)")
        self.duration_spinbox.pack(side="left")

        # Option B: By Number of Equal Parts
        self.rad_parts = ctk.CTkRadioButton(
            mode_frame,
            text="Split into Equal Parts (e.g., Part 1, Part 2, Part 3...)",
            variable=self.split_mode_var,
            value="parts",
            command=self._on_mode_toggled,
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_parts.pack(anchor="w", padx=12, pady=4)

        self.parts_input_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.parts_input_frame.pack(anchor="w", padx=36, pady=(0, 6))

        parts_lbl = ctk.CTkLabel(self.parts_input_frame, text="Number of Parts:", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY)
        parts_lbl.pack(side="left", padx=(0, 8))

        self.parts_menu = ctk.CTkOptionMenu(
            self.parts_input_frame,
            values=["2 Parts (Half)", "3 Parts", "4 Parts", "5 Parts", "6 Parts", "8 Parts", "10 Parts"],
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG,
            button_color=Theme.ACCENT_CYAN,
            width=180,
            height=28
        )
        self.parts_menu.set("2 Parts (Half)")
        self.parts_menu.pack(side="left")

        # Option C: Custom Trim Range
        self.rad_trim = ctk.CTkRadioButton(
            mode_frame,
            text="Custom Start / End Cut Range",
            variable=self.split_mode_var,
            value="trim",
            command=self._on_mode_toggled,
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_trim.pack(anchor="w", padx=12, pady=4)

        self.trim_input_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.trim_input_frame.pack(anchor="w", padx=36, pady=(0, 10))

        start_lbl = ctk.CTkLabel(self.trim_input_frame, text="Start (s):", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY)
        start_lbl.pack(side="left", padx=(0, 4))
        self.trim_start_entry = ctk.CTkEntry(self.trim_input_frame, width=60, height=26, font=Theme.FONT_SMALL)
        self.trim_start_entry.insert(0, "0.0")
        self.trim_start_entry.pack(side="left", padx=(0, 12))

        end_lbl = ctk.CTkLabel(self.trim_input_frame, text="End (s):", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY)
        end_lbl.pack(side="left", padx=(0, 4))
        self.trim_end_entry = ctk.CTkEntry(self.trim_input_frame, width=60, height=26, font=Theme.FONT_SMALL)
        self.trim_end_entry.insert(0, "60.0")
        self.trim_end_entry.pack(side="left")

        # 3. Output Directory
        out_lbl = ctk.CTkLabel(container, text="Save Clips To:", font=Theme.FONT_BODY, text_color=Theme.TEXT_PRIMARY)
        out_lbl.grid(row=5, column=0, sticky="w", padx=16, pady=4)

        self.default_out_dir = Path.home() / "Desktop" / "Split_Videos"
        self.out_entry = ctk.CTkEntry(
            container,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            border_color=Theme.CARD_BORDER,
            height=32
        )
        self.out_entry.insert(0, str(self.default_out_dir))
        self.out_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=4)

        self.out_btn = ctk.CTkButton(
            container,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=32,
            command=self._on_browse_output
        )
        self.out_btn.grid(row=5, column=2, padx=(0, 16), pady=4)

        # 4. Toggles: Denoise Audio while splitting
        self.denoise_chk = ctk.CTkCheckBox(
            container,
            text="Apply Background Noise Reduction to Audio during splitting",
            font=Theme.FONT_SMALL,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.denoise_chk.grid(row=6, column=0, columnspan=3, sticky="w", padx=16, pady=4)

        # 5. Progress Bar & Status
        self.prog_bar = ctk.CTkProgressBar(container, progress_color=Theme.ACCENT_CLEAN, height=10)
        self.prog_bar.set(0.0)
        self.prog_bar.grid(row=7, column=0, columnspan=3, sticky="ew", padx=16, pady=(8, 2))

        self.status_lbl = ctk.CTkLabel(container, text="Ready to split video.", font=Theme.FONT_SMALL, text_color=Theme.TEXT_SECONDARY)
        self.status_lbl.grid(row=8, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 8))

        # 6. Action Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.grid(row=9, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 12))
        btn_box.grid_columnconfigure(0, weight=1)

        self.open_dir_btn = ctk.CTkButton(
            btn_box,
            text="📂 Open Output Folder",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            width=160,
            height=36,
            command=self._open_output_dir
        )
        self.open_dir_btn.pack(side="left")

        self.split_btn = ctk.CTkButton(
            btn_box,
            text="✂️  START SPLITTING",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CLEAN,
            hover_color=Theme.ACCENT_CLEAN_HOVER,
            text_color="#FFFFFF",
            width=180,
            height=36,
            command=self._start_split_thread
        )
        self.split_btn.pack(side="right")

    def _on_mode_toggled(self) -> None:
        pass

    def _on_browse_video(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Video to Split",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.m4v *.ts"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            self._set_selected_video(Path(file_path))

    def _set_selected_video(self, path: Path) -> None:
        self.video_entry.delete(0, "end")
        self.video_entry.insert(0, str(path))
        try:
            dur = FFmpegHelper.get_media_duration(path)
            self.video_duration = dur
            mins = int(dur // 60)
            secs = int(dur % 60)
            self.info_label.configure(text=f"Duration: {mins:02d}:{secs:02d} ({dur:.1f}s) | Lossless Stream-Copy Ready")
            self.trim_end_entry.delete(0, "end")
            self.trim_end_entry.insert(0, f"{dur:.1f}")
        except Exception:
            self.info_label.configure(text="Video loaded.")

    def _on_browse_output(self) -> None:
        sel = filedialog.askdirectory(title="Select Destination Folder")
        if sel:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, str(sel))

    def _start_split_thread(self) -> None:
        if self.is_processing:
            return

        v_text = self.video_entry.get().strip()
        if not v_text or not Path(v_text).exists():
            self.status_lbl.configure(text="[Error] Please select a valid video file first.", text_color=Theme.ACCENT_DIRTY)
            return

        out_text = self.out_entry.get().strip()
        if not out_text:
            out_text = str(self.default_out_dir)

        v_path = Path(v_text)
        out_dir = Path(out_text)
        out_dir.mkdir(parents=True, exist_ok=True)

        mode = self.split_mode_var.get()
        denoise = bool(self.denoise_chk.get())

        self.is_processing = True
        self.split_btn.configure(state="disabled", text="Splitting...")
        self.browse_btn.configure(state="disabled")

        def _worker():
            try:
                def _prog(pct: float, msg: str):
                    self.after(0, lambda: self._update_ui_progress(pct, msg))

                if mode == "duration":
                    dur_val_text = self.duration_spinbox.get()
                    # Extract number from "30 Seconds (...)"
                    sec = float(dur_val_text.split()[0])
                    results = VideoEngine.split_video_by_duration(
                        video_path=v_path,
                        segment_duration_sec=sec,
                        output_dir=out_dir,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )
                elif mode == "parts":
                    part_text = self.parts_menu.get()
                    num = int(part_text.split()[0])
                    results = VideoEngine.split_video_by_parts(
                        video_path=v_path,
                        num_parts=num,
                        output_dir=out_dir,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )
                else:
                    # Custom Trim
                    s_sec = float(self.trim_start_entry.get().strip())
                    e_sec = float(self.trim_end_entry.get().strip())
                    out_clip = out_dir / f"{v_path.stem}_trimmed{v_path.suffix}"
                    results = [VideoEngine.trim_video_range(
                        video_path=v_path,
                        start_sec=s_sec,
                        end_sec=e_sec,
                        output_path=out_clip,
                        denoise=denoise,
                        config=self.denoise_config,
                        progress_callback=_prog
                    )]

                self.after(0, lambda: self._on_finish_success(results))
            except Exception as ex:
                logger.error(f"Video splitting error: {ex}")
                self.after(0, lambda: self._on_finish_error(str(ex)))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_ui_progress(self, percent: float, msg: str) -> None:
        self.prog_bar.set(min(max(percent / 100.0, 0.0), 1.0))
        self.status_lbl.configure(text=f"[{int(percent)}%] {msg}", text_color=Theme.TEXT_SECONDARY)

    def _on_finish_success(self, created_files: list[Path]) -> None:
        self.is_processing = False
        self.split_btn.configure(state="normal", text="✂️  START SPLITTING")
        self.browse_btn.configure(state="normal")
        self.prog_bar.set(1.0)
        self.status_lbl.configure(
            text=f"✅ Done! Successfully generated {len(created_files)} clips in output directory.",
            text_color=Theme.ACCENT_CLEAN
        )
        if self.on_success:
            self.on_success(created_files)

    def _on_finish_error(self, err_msg: str) -> None:
        self.is_processing = False
        self.split_btn.configure(state="normal", text="✂️  START SPLITTING")
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

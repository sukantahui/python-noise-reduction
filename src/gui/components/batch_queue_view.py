"""Batch queue and export manager widget."""
import os
import subprocess
import sys
import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional, List
from tkinter import filedialog
from src.gui.theme import Theme
from src.utils.logger import get_logger

logger = get_logger("BatchQueueView")


class BatchQueueView(ctk.CTkFrame):
    """Export and batch processing status panel."""

    EXPORT_MODES = [
        "Lossless Video Remux (-c:v copy)",
        "Cleaned Audio (WAV Lossless)",
        "Cleaned Audio (MP3 320k)",
        "Cleaned Audio (FLAC Studio)",
        "Cleaned Audio (AAC / M4A)",
        "Cleaned Audio (OGG Vorbis)",
        "Noise Track Only (Difference WAV)",
        "Raw Original Audio (WAV)",
        "Raw Original Audio (MP3 320k)",
    ]

    def __init__(
        self,
        master: any,
        on_export_start: Callable[[Path, str, str], None],
        on_extract_audio_request: Optional[Callable[[], None]] = None,
        on_split_video_request: Optional[Callable[[], None]] = None,
        on_split_audio_request: Optional[Callable[[], None]] = None,
        on_remove_selection_request: Optional[Callable[[], None]] = None,
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
        self.on_export_start = on_export_start
        self.on_extract_audio_request = on_extract_audio_request
        self.on_split_video_request = on_split_video_request
        self.on_split_audio_request = on_split_audio_request
        self.on_remove_selection_request = on_remove_selection_request
        self.output_dir: Path = Path.home() / "Desktop" / "Cleaned_Audio_Output"

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Row 0: Output Directory
        self.dir_label = ctk.CTkLabel(
            self,
            text="📁 Output Folder:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY
        )
        self.dir_label.grid(row=0, column=0, padx=(12, 6), pady=(10, 4), sticky="w")

        self.dir_entry = ctk.CTkEntry(
            self,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            text_color=Theme.TEXT_PRIMARY,
            border_color=Theme.CARD_BORDER,
            height=30
        )
        self.dir_entry.insert(0, str(self.output_dir))
        self.dir_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=(10, 4))

        self.dir_btn = ctk.CTkButton(
            self,
            text="Browse...",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=80,
            height=30,
            command=self._on_browse_dir
        )
        self.dir_btn.grid(row=0, column=2, padx=(6, 12), pady=(10, 4))

        # Row 1: Format Options & Export Button
        self.opts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.opts_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 6))
        self.opts_frame.grid_columnconfigure(1, weight=1)

        self.fmt_label = ctk.CTkLabel(
            self.opts_frame,
            text="Export Mode:",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.fmt_label.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.video_action_menu = ctk.CTkOptionMenu(
            self.opts_frame,
            values=self.EXPORT_MODES,
            font=Theme.FONT_SMALL,
            fg_color=Theme.BG_DARK,
            button_color=Theme.ACCENT_CYAN,
            width=210,
            height=28
        )
        self.video_action_menu.set("Lossless Video Remux (-c:v copy)")
        self.video_action_menu.grid(row=0, column=1, sticky="w", padx=2)

        self.extract_tool_btn = ctk.CTkButton(
            self.opts_frame,
            text="🎵 Extract Sound...",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color=Theme.ACCENT_CYAN,
            width=120,
            height=32,
            command=self._on_extract_tool_click
        )
        self.extract_tool_btn.grid(row=0, column=2, padx=2)

        self.split_tool_btn = ctk.CTkButton(
            self.opts_frame,
            text="✂️ Split Video...",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color="#A78BFA",
            width=110,
            height=32,
            command=self._on_split_tool_click
        )
        self.split_tool_btn.grid(row=0, column=3, padx=2)

        self.split_audio_tool_btn = ctk.CTkButton(
            self.opts_frame,
            text="✂️ Split Audio...",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color="#A78BFA",
            width=105,
            height=32,
            command=self._on_split_audio_tool_click
        )
        self.split_audio_tool_btn.grid(row=0, column=4, padx=2)

        self.cut_selection_tool_btn = ctk.CTkButton(
            self.opts_frame,
            text="✂️ Cut Selection...",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color=Theme.ACCENT_YELLOW,
            width=115,
            height=32,
            command=self._on_cut_selection_tool_click
        )
        self.cut_selection_tool_btn.grid(row=0, column=5, padx=2)

        self.open_folder_btn = ctk.CTkButton(
            self.opts_frame,
            text="📂 Output Folder",
            font=Theme.FONT_SMALL,
            fg_color="#374151",
            hover_color="#4B5563",
            width=105,
            height=32,
            command=self.open_output_folder
        )
        self.open_folder_btn.grid(row=0, column=6, padx=2)

        self.export_btn = ctk.CTkButton(
            self.opts_frame,
            text="🚀  EXPORT",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CLEAN,
            hover_color=Theme.ACCENT_CLEAN_HOVER,
            text_color="#FFFFFF",
            corner_radius=Theme.CORNER_RADIUS_SM,
            width=115,
            height=34,
            command=self._on_export_click
        )
        self.export_btn.grid(row=0, column=7, padx=(2, 0))

        # Row 2: Progress Bar and Status Label
        self.prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.prog_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(2, 10))
        self.prog_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            self.prog_frame,
            progress_color=Theme.ACCENT_CLEAN,
            height=10
        )
        self.progress_bar.set(0.0)
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(2, 2))

        self.status_label = ctk.CTkLabel(
            self.prog_frame,
            text="Ready to process.",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.status_label.grid(row=1, column=0, sticky="w")

    def _on_browse_dir(self) -> None:
        sel = filedialog.askdirectory(title="Select Output Directory")
        if sel:
            self.output_dir = Path(sel)
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, str(self.output_dir))

    def _on_extract_tool_click(self) -> None:
        if self.on_extract_audio_request:
            self.on_extract_audio_request()

    def _on_split_video_request(self) -> None:
        pass

    def _on_split_tool_click(self) -> None:
        if self.on_split_video_request:
            self.on_split_video_request()

    def _on_split_audio_tool_click(self) -> None:
        if self.on_split_audio_request:
            self.on_split_audio_request()

    def _on_cut_selection_tool_click(self) -> None:
        if self.on_remove_selection_request:
            self.on_remove_selection_request()

    def _on_export_click(self) -> None:
        out_dir = Path(self.dir_entry.get().strip())
        video_mode = self.video_action_menu.get()
        self.export_btn.configure(state="disabled", text="Processing...")
        self.on_export_start(out_dir, video_mode, "denoised")

    def update_progress(self, percent: float, message: str) -> None:
        """Thread-safe UI progress update."""
        self.progress_bar.set(min(max(percent / 100.0, 0.0), 1.0))
        self.status_label.configure(text=f"[{int(percent)}%] {message}")
        if percent >= 100.0 or percent <= 0.0:
            self.export_btn.configure(state="normal", text="🚀  EXPORT MEDIA")

    def open_output_folder(self) -> None:
        """Opens output directory in native OS file explorer."""
        out_dir = Path(self.dir_entry.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(out_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(out_dir)])
            else:
                subprocess.Popen(["xdg-open", str(out_dir)])
        except Exception as ex:
            logger.warning(f"Failed to open folder: {ex}")

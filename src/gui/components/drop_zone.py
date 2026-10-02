"""Drag-and-drop media import widget with file picker and format badge display."""
import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional
from tkinter import filedialog
from src.gui.theme import Theme
from src.utils.ffmpeg_helper import FFmpegHelper


class DropZone(ctk.CTkFrame):
    """Media dropzone and file selection card."""

    SUPPORTED_EXTENSIONS = (
        ("Media Files", "*.wav *.mp3 *.flac *.aac *.m4a *.ogg *.mp4 *.mkv *.mov *.avi *.webm"),
        ("Audio Files", "*.wav *.mp3 *.flac *.aac *.m4a *.ogg"),
        ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm"),
        ("All Files", "*.*")
    )

    def __init__(
        self,
        master: any,
        on_file_selected: Callable[[Path], None],
        on_extract_audio: Optional[Callable[[Optional[Path]], None]] = None,
        on_split_video: Optional[Callable[[Optional[Path]], None]] = None,
        on_split_audio: Optional[Callable[[Optional[Path]], None]] = None,
        on_remove_selection: Optional[Callable[[Optional[Path]], None]] = None,
        on_extract_vocals: Optional[Callable[[Optional[Path]], None]] = None,
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
        self.on_file_selected = on_file_selected
        self.on_extract_audio = on_extract_audio
        self.on_split_video = on_split_video
        self.on_split_audio = on_split_audio
        self.on_remove_selection = on_remove_selection
        self.on_extract_vocals = on_extract_vocals
        self.current_file: Optional[Path] = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Container Frame
        self.inner_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
            corner_radius=Theme.CORNER_RADIUS_MD
        )
        self.inner_frame.pack(fill="both", expand=True, padx=16, pady=14)

        # Title & Icon
        self.icon_label = ctk.CTkLabel(
            self.inner_frame,
            text="📁  Drag & Drop Media File Here",
            font=Theme.FONT_TITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        self.icon_label.pack(pady=(2, 4))

        # Subtitle formats
        self.sub_label = ctk.CTkLabel(
            self.inner_frame,
            text="Supports Video (MP4, MKV, MOV, AVI) & Audio (WAV, MP3, FLAC, M4A, OGG)",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY
        )
        self.sub_label.pack(pady=(0, 10))

        # Buttons row
        self.btn_row = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        self.btn_row.pack(pady=2)

        self.browse_btn = ctk.CTkButton(
            self.btn_row,
            text="Browse Media...",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CYAN,
            hover_color=Theme.ACCENT_CYAN_HOVER,
            text_color="#FFFFFF",
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_browse_click,
            height=32,
            width=135
        )
        self.browse_btn.pack(side="left", padx=3)

        self.extract_audio_btn = ctk.CTkButton(
            self.btn_row,
            text="🎵 Extract Sound...",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_extract_audio_click,
            height=32,
            width=135
        )
        self.extract_audio_btn.pack(side="left", padx=3)

        self.split_video_btn = ctk.CTkButton(
            self.btn_row,
            text="✂️ Split Video...",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_split_video_click,
            height=32,
            width=125
        )
        self.split_video_btn.pack(side="left", padx=3)

        self.split_audio_btn = ctk.CTkButton(
            self.btn_row,
            text="✂️ Split Audio...",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_split_audio_click,
            height=32,
            width=120
        )
        self.split_audio_btn.pack(side="left", padx=3)

        self.remove_selection_btn = ctk.CTkButton(
            self.btn_row,
            text="✂️ Cut Selection...",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_remove_selection_click,
            height=32,
            width=120
        )
        self.remove_selection_btn.pack(side="left", padx=3)

        self.extract_vocals_btn = ctk.CTkButton(
            self.btn_row,
            text="🎤 Extract Vocals...",
            font=Theme.FONT_BODY,
            fg_color="#374151",
            hover_color="#4B5563",
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_extract_vocals_click,
            height=32,
            width=135
        )
        self.extract_vocals_btn.pack(side="left", padx=3)

        # Loaded File Metadata Badge Frame (Hidden initially)
        self.info_card = ctk.CTkFrame(
            self.inner_frame,
            fg_color=Theme.BG_DARK,
            corner_radius=Theme.CORNER_RADIUS_SM,
            border_color=Theme.CARD_BORDER,
            border_width=1
        )
        self.info_card.grid_columnconfigure(0, weight=1)

        self.card_left = ctk.CTkFrame(self.info_card, fg_color="transparent")
        self.card_left.pack(side="left", fill="both", expand=True, padx=12, pady=6)

        self.file_title_label = ctk.CTkLabel(
            self.card_left,
            text="",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.ACCENT_CLEAN,
            anchor="w"
        )
        self.file_title_label.pack(anchor="w", pady=(0, 2))

        self.file_meta_label = ctk.CTkLabel(
            self.card_left,
            text="",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_SECONDARY,
            anchor="w"
        )
        self.file_meta_label.pack(anchor="w")

        # Quick Cut Selection Chip
        self.quick_cut_selection_btn = ctk.CTkButton(
            self.info_card,
            text="✂️ Cut Selection",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color=Theme.ACCENT_YELLOW,
            width=100,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_remove_selection_click
        )

        # Quick Split Video Chip
        self.quick_split_video_btn = ctk.CTkButton(
            self.info_card,
            text="✂️ Split Video",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color="#A78BFA",
            width=100,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_split_video_click
        )

        # Quick Split Audio Chip
        self.quick_split_audio_btn = ctk.CTkButton(
            self.info_card,
            text="✂️ Split Audio",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color="#A78BFA",
            width=100,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_split_audio_click
        )

        # Quick Extract Audio Chip for Loaded Videos
        self.quick_extract_btn = ctk.CTkButton(
            self.info_card,
            text="🎵 Extract Audio",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color=Theme.ACCENT_CYAN,
            width=105,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_extract_audio_click
        )

        # Quick Extract Vocals Chip
        self.quick_extract_vocals_btn = ctk.CTkButton(
            self.info_card,
            text="🎤 Vocals Only",
            font=Theme.FONT_SMALL,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color="#F472B6",
            width=100,
            height=28,
            corner_radius=Theme.CORNER_RADIUS_SM,
            command=self._on_extract_vocals_click
        )

    def _on_browse_click(self) -> None:
        file_path_str = filedialog.askopenfilename(
            title="Select Audio or Video File",
            filetypes=self.SUPPORTED_EXTENSIONS
        )
        if file_path_str:
            path = Path(file_path_str)
            self.set_loaded_file(path)
            self.on_file_selected(path)

    def _on_extract_audio_click(self) -> None:
        if self.on_extract_audio:
            self.on_extract_audio(self.current_file)

    def _on_split_video_click(self) -> None:
        if self.on_split_video:
            self.on_split_video(self.current_file)

    def _on_split_audio_click(self) -> None:
        if self.on_split_audio:
            self.on_split_audio(self.current_file)

    def _on_remove_selection_click(self) -> None:
        if self.on_remove_selection:
            self.on_remove_selection(self.current_file)

    def _on_extract_vocals_click(self) -> None:
        if self.on_extract_vocals:
            self.on_extract_vocals(self.current_file)

    def set_loaded_file(self, path: Path, metadata_str: str = "") -> None:
        """Updates UI display with loaded file information."""
        self.current_file = path
        is_video = FFmpegHelper.is_video_file(path)
        tag = "[VIDEO TRACK]" if is_video else "[AUDIO TRACK]"

        self.file_title_label.configure(text=f"{tag} {path.name}")
        size_mb = path.stat().st_size / (1024 * 1024) if path.exists() else 0.0

        if not metadata_str:
            meta = f"Size: {size_mb:.2f} MB | Format: {path.suffix.upper().lstrip('.')}"
        else:
            meta = f"{metadata_str} | Size: {size_mb:.2f} MB"

        self.file_meta_label.configure(text=meta)

        self.quick_extract_vocals_btn.pack(side="right", padx=(4, 12), pady=6)
        self.quick_cut_selection_btn.pack(side="right", padx=4, pady=6)
        if is_video:
            self.quick_split_audio_btn.pack_forget()
            self.quick_split_video_btn.pack(side="right", padx=4, pady=6)
            self.quick_extract_btn.pack(side="right", padx=4, pady=6)
        else:
            self.quick_split_video_btn.pack_forget()
            self.quick_extract_btn.pack_forget()
            self.quick_split_audio_btn.pack(side="right", padx=4, pady=6)

        self.info_card.pack(fill="x", expand=True, pady=(8, 0))

    def clear(self) -> None:
        """Clears loaded file card."""
        self.current_file = None
        self.info_card.pack_forget()

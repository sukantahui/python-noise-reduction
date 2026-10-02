"""Settings panel widget with algorithm presets and fine-grained DSP parameter controls."""
import customtkinter as ctk
from typing import Callable, Optional
from src.gui.theme import Theme
from src.core.audio_engine import AudioDenoiseEngine, DenoiseConfig


class SettingsPanel(ctk.CTkScrollableFrame):
    """Panel containing DSP sliders, algorithm mode toggles, presets, and action triggers."""

    def __init__(
        self,
        master: any,
        on_settings_change: Optional[Callable[[DenoiseConfig], None]] = None,
        on_preview_request: Optional[Callable[[], None]] = None,
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
        self.on_settings_change = on_settings_change
        self.on_preview_request = on_preview_request
        self.config = DenoiseConfig()

        self._build_ui()

    def _build_ui(self) -> None:
        # Title
        self.title_label = ctk.CTkLabel(
            self,
            text="⚙️  DSP Denoising Parameters",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.TEXT_PRIMARY
        )
        self.title_label.pack(anchor="w", padx=10, pady=(4, 10))

        # 1. Preset Dropdown
        self.preset_label = ctk.CTkLabel(
            self,
            text="Studio Algorithm Preset:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_SECONDARY
        )
        self.preset_label.pack(anchor="w", padx=10, pady=(2, 2))

        preset_names = list(AudioDenoiseEngine.PRESETS.keys())
        self.preset_menu = ctk.CTkOptionMenu(
            self,
            values=preset_names,
            command=self._on_preset_selected,
            font=Theme.FONT_BODY,
            fg_color=Theme.BG_DARK,
            button_color=Theme.ACCENT_CYAN,
            button_hover_color=Theme.ACCENT_CYAN_HOVER,
            dropdown_fg_color=Theme.CARD_BG,
            height=32
        )
        self.preset_menu.set("Default Studio Voice")
        self.preset_menu.pack(fill="x", padx=10, pady=(0, 10))

        # 2. Reduction Strength Slider
        self.strength_header = ctk.CTkFrame(self, fg_color="transparent")
        self.strength_header.pack(fill="x", padx=10, pady=(4, 0))
        self.strength_title = ctk.CTkLabel(
            self.strength_header,
            text="Reduction Strength:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY
        )
        self.strength_title.pack(side="left")
        self.strength_val_lbl = ctk.CTkLabel(
            self.strength_header,
            text="80%",
            font=Theme.FONT_SUBTITLE,
            text_color=Theme.ACCENT_CYAN
        )
        self.strength_val_lbl.pack(side="right")

        self.strength_slider = ctk.CTkSlider(
            self,
            from_=0.10,
            to=1.00,
            number_of_steps=90,
            progress_color=Theme.ACCENT_CYAN,
            button_color=Theme.ACCENT_CYAN,
            command=self._on_strength_drag
        )
        self.strength_slider.set(0.80)
        self.strength_slider.pack(fill="x", padx=10, pady=(2, 10))

        # 3. Noise Profile Mode (Stationary vs Dynamic)
        self.mode_label = ctk.CTkLabel(
            self,
            text="Noise Profiling Mode:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_SECONDARY
        )
        self.mode_label.pack(anchor="w", padx=10, pady=(2, 2))

        self.mode_var = ctk.StringVar(value="stationary")
        self.mode_row = ctk.CTkFrame(self, fg_color="transparent")
        self.mode_row.pack(fill="x", padx=10, pady=(0, 10))

        self.rad_stat = ctk.CTkRadioButton(
            self.mode_row,
            text="Stationary (Fans/Hiss)",
            variable=self.mode_var,
            value="stationary",
            command=self._on_mode_change,
            font=Theme.FONT_SMALL,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_stat.pack(side="left", padx=(0, 8))

        self.rad_dyn = ctk.CTkRadioButton(
            self.mode_row,
            text="Dynamic (Wind/Street)",
            variable=self.mode_var,
            value="dynamic",
            command=self._on_mode_change,
            font=Theme.FONT_SMALL,
            fg_color=Theme.ACCENT_CLEAN
        )
        self.rad_dyn.pack(side="left")

        # 4. High-Pass Filter (Rumble Cut)
        self.hp_header = ctk.CTkFrame(self, fg_color="transparent")
        self.hp_header.pack(fill="x", padx=10, pady=(4, 0))
        self.hp_title = ctk.CTkLabel(
            self.hp_header,
            text="High-Pass Filter (Rumble Cut):",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY
        )
        self.hp_title.pack(side="left")
        self.hp_val_lbl = ctk.CTkLabel(
            self.hp_header,
            text="80 Hz",
            font=Theme.FONT_BODY,
            text_color=Theme.ACCENT_CYAN
        )
        self.hp_val_lbl.pack(side="right")

        self.hp_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=250,
            number_of_steps=50,
            progress_color=Theme.ACCENT_CYAN,
            button_color=Theme.ACCENT_CYAN,
            command=self._on_hp_drag
        )
        self.hp_slider.set(80)
        self.hp_slider.pack(fill="x", padx=10, pady=(2, 10))

        # 5. Low-Pass Filter (High Hiss Cut)
        self.lp_header = ctk.CTkFrame(self, fg_color="transparent")
        self.lp_header.pack(fill="x", padx=10, pady=(4, 0))
        self.lp_title = ctk.CTkLabel(
            self.lp_header,
            text="Low-Pass Filter (Hiss Cut):",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY
        )
        self.lp_title.pack(side="left")
        self.lp_val_lbl = ctk.CTkLabel(
            self.lp_header,
            text="Disabled (Full)",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_SECONDARY
        )
        self.lp_val_lbl.pack(side="right")

        self.lp_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=20000,
            number_of_steps=40,
            progress_color=Theme.ACCENT_CYAN,
            button_color=Theme.ACCENT_CYAN,
            command=self._on_lp_drag
        )
        self.lp_slider.set(0)
        self.lp_slider.pack(fill="x", padx=10, pady=(2, 10))

        # 6. Time Smoothing & Noise Gate
        self.smooth_header = ctk.CTkFrame(self, fg_color="transparent")
        self.smooth_header.pack(fill="x", padx=10, pady=(4, 0))
        self.smooth_title = ctk.CTkLabel(
            self.smooth_header,
            text="Temporal Mask Smoothing:",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_PRIMARY
        )
        self.smooth_title.pack(side="left")
        self.smooth_val_lbl = ctk.CTkLabel(
            self.smooth_header,
            text="3 frames",
            font=Theme.FONT_BODY,
            text_color=Theme.ACCENT_CYAN
        )
        self.smooth_val_lbl.pack(side="right")

        self.smooth_slider = ctk.CTkSlider(
            self,
            from_=1,
            to=8,
            number_of_steps=7,
            progress_color=Theme.ACCENT_CYAN,
            button_color=Theme.ACCENT_CYAN,
            command=self._on_smooth_drag
        )
        self.smooth_slider.set(3)
        self.smooth_slider.pack(fill="x", padx=10, pady=(2, 10))

        # 7. Checkboxes: Peak Normalization, Noise Gate, Electrical Notches
        self.toggles_frame = ctk.CTkFrame(self, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        self.toggles_frame.pack(fill="x", padx=10, pady=(6, 12))

        self.norm_chk = ctk.CTkCheckBox(
            self.toggles_frame,
            text="Peak Normalize to -1.0 dBFS",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN,
            command=self._on_toggle_change
        )
        self.norm_chk.select()
        self.norm_chk.pack(anchor="w", padx=10, pady=(8, 4))

        self.gate_chk = ctk.CTkCheckBox(
            self.toggles_frame,
            text="Enable Soft Noise Gate (-48 dB)",
            font=Theme.FONT_BODY,
            fg_color=Theme.ACCENT_CLEAN,
            command=self._on_toggle_change
        )
        self.gate_chk.select()
        self.gate_chk.pack(anchor="w", padx=10, pady=4)

        self.notch_50_chk = ctk.CTkCheckBox(
            self.toggles_frame,
            text="Cut 50Hz Mains Hum (EU/UK/Asia)",
            font=Theme.FONT_SMALL,
            fg_color=Theme.ACCENT_CLEAN,
            command=self._on_toggle_change
        )
        self.notch_50_chk.pack(anchor="w", padx=10, pady=(4, 4))

        self.notch_60_chk = ctk.CTkCheckBox(
            self.toggles_frame,
            text="Cut 60Hz Mains Hum (US/Americas)",
            font=Theme.FONT_SMALL,
            fg_color=Theme.ACCENT_CLEAN,
            command=self._on_toggle_change
        )
        self.notch_60_chk.pack(anchor="w", padx=10, pady=(4, 8))

        # 8. Re-calculate / Preview Denoise Button
        self.preview_btn = ctk.CTkButton(
            self,
            text="⚡  APPLY & UPDATE PREVIEW",
            font=Theme.FONT_SUBTITLE,
            fg_color=Theme.ACCENT_CLEAN,
            hover_color=Theme.ACCENT_CLEAN_HOVER,
            text_color="#FFFFFF",
            corner_radius=Theme.CORNER_RADIUS_SM,
            height=38,
            command=self._on_preview_click
        )
        self.preview_btn.pack(fill="x", padx=10, pady=(4, 10))

    def _on_preset_selected(self, preset_name: str) -> None:
        p = AudioDenoiseEngine.get_preset(preset_name)
        self.config = p
        self.strength_slider.set(p.reduction_strength)
        self.strength_val_lbl.configure(text=f"{int(p.reduction_strength * 100)}%")
        self.mode_var.set("stationary" if p.stationary_mode else "dynamic")
        self.hp_slider.set(p.high_pass_hz)
        self.hp_val_lbl.configure(text=f"{int(p.high_pass_hz)} Hz" if p.high_pass_hz > 0 else "Off")
        self.lp_slider.set(p.low_pass_hz)
        self.lp_val_lbl.configure(text=f"{int(p.low_pass_hz)} Hz" if p.low_pass_hz > 0 else "Disabled (Full)")
        self.smooth_slider.set(p.time_smoothing)
        self.smooth_val_lbl.configure(text=f"{p.time_smoothing} frames")

        if p.normalize:
            self.norm_chk.select()
        else:
            self.norm_chk.deselect()

        if p.noise_gate_db > -80:
            self.gate_chk.select()
        else:
            self.gate_chk.deselect()

        self._notify_change()

    def _on_strength_drag(self, val: float) -> None:
        self.config.reduction_strength = float(val)
        self.strength_val_lbl.configure(text=f"{int(val * 100)}%")
        self._notify_change()

    def _on_mode_change(self) -> None:
        self.config.stationary_mode = (self.mode_var.get() == "stationary")
        self._notify_change()

    def _on_hp_drag(self, val: float) -> None:
        hz = int(val)
        self.config.high_pass_hz = float(hz)
        self.hp_val_lbl.configure(text=f"{hz} Hz" if hz > 0 else "Off")
        self._notify_change()

    def _on_lp_drag(self, val: float) -> None:
        hz = int(val)
        self.config.low_pass_hz = float(hz)
        self.lp_val_lbl.configure(text=f"{hz} Hz" if hz > 0 else "Disabled (Full)")
        self._notify_change()

    def _on_smooth_drag(self, val: float) -> None:
        frames = int(val)
        self.config.time_smoothing = frames
        self.smooth_val_lbl.configure(text=f"{frames} frames")
        self._notify_change()

    def _on_toggle_change(self) -> None:
        self.config.normalize = bool(self.norm_chk.get())
        self.config.noise_gate_db = -48.0 if bool(self.gate_chk.get()) else -90.0
        self.config.notch_50hz = bool(self.notch_50_chk.get())
        self.config.notch_60hz = bool(self.notch_60_chk.get())
        self._notify_change()

    def _notify_change(self) -> None:
        if self.on_settings_change:
            self.on_settings_change(self.config)

    def _on_preview_click(self) -> None:
        if self.on_preview_request:
            self.on_preview_request()

    def get_config(self) -> DenoiseConfig:
        return self.config

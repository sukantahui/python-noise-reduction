"""About Dialog window displaying software and creator information."""
import webbrowser
from pathlib import Path
import customtkinter as ctk
from PIL import Image
from src.gui.theme import Theme

class AboutDialog(ctk.CTkToplevel):
    """Modern modal dialog displaying Coder & AccoTax branding and app details."""

    def __init__(self, parent: ctk.CTk) -> None:
        super().__init__(parent)

        self.title("About CNAT NOISERELIEF")
        self.geometry("480x460")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_DARK)

        # Modal behavior
        self.transient(parent)
        self.grab_set()

        # Center on parent window
        self._center_window(parent)

        self._build_ui()

    def _center_window(self, parent: ctk.CTk) -> None:
        parent.update_idletasks()
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        w, h = 480, 460
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

        # Logo
        logo_path = Path(__file__).parent.parent / "assets" / "logo.png"
        if not logo_path.exists():
            logo_path = Path("assets/logo.png")

        if logo_path.exists():
            try:
                pil_img = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(72, 72))
                logo_label = ctk.CTkLabel(container, image=logo_ctk, text="")
                logo_label.pack(pady=(16, 6))
            except Exception:
                pass

        # App Name & Subtitle
        app_title = ctk.CTkLabel(
            container,
            text="CNAT NOISERELIEF",
            font=("Segoe UI", 18, "bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        app_title.pack()

        app_desc = ctk.CTkLabel(
            container,
            text="High-Fidelity Audio & Video Noise Reduction GUI",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT_SECONDARY
        )
        app_desc.pack(pady=(2, 12))

        # Divider
        divider = ctk.CTkFrame(container, fg_color=Theme.CARD_BORDER, height=1)
        divider.pack(fill="x", padx=24, pady=(0, 12))

        # Creator Card
        creator_frame = ctk.CTkFrame(container, fg_color=Theme.BG_DARK, corner_radius=Theme.CORNER_RADIUS_SM)
        creator_frame.pack(fill="x", padx=20, pady=4)

        created_by_lbl = ctk.CTkLabel(
            creator_frame,
            text="Created by",
            font=Theme.FONT_SMALL,
            text_color=Theme.TEXT_MUTED
        )
        created_by_lbl.pack(pady=(8, 0))

        company_lbl = ctk.CTkLabel(
            creator_frame,
            text="Coder & AccoTax",
            font=("Segoe UI", 15, "bold"),
            text_color=Theme.ACCENT_CYAN
        )
        company_lbl.pack(pady=(0, 4))

        # Website Button / Link
        site_btn = ctk.CTkButton(
            creator_frame,
            text="🌐  www.codernaccotax.co.in",
            font=("Segoe UI", 11, "underline"),
            fg_color="transparent",
            hover_color=Theme.CARD_BG_HOVER,
            text_color=Theme.ACCENT_CYAN,
            cursor="hand2",
            height=26,
            command=lambda: webbrowser.open_new_tab("https://www.codernaccotax.co.in")
        )
        site_btn.pack(pady=2)

        # Phone Info
        phone_lbl = ctk.CTkLabel(
            creator_frame,
            text="📞  Ph: 7003756860",
            font=("Segoe UI", 11, "bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        phone_lbl.pack(pady=(2, 10))

        # Close Button
        close_btn = ctk.CTkButton(
            container,
            text="Close",
            font=Theme.FONT_BODY,
            fg_color=Theme.CARD_BG_HOVER,
            hover_color=Theme.CARD_BORDER,
            text_color=Theme.TEXT_PRIMARY,
            width=100,
            command=self.destroy
        )
        close_btn.pack(pady=(16, 8))

"""Design tokens and theme definitions for Cyber-Acoustic Studio Dark Theme."""

class Theme:
    """Color palette and styling constants for CustomTkinter widgets."""

    # Backgrounds & Surfaces
    BG_DARK = "#111827"           # Root window background (Dark Slate)
    CARD_BG = "#1F2937"           # Studio card container background
    CARD_BG_HOVER = "#2D3748"     # Hover state for card surfaces
    CARD_BORDER = "#374151"       # Subtle border lines
    CANVAS_BG = "#0B0F19"         # Ultra-dark background for waveform canvas

    # Brand & Accent Colors
    ACCENT_CLEAN = "#10B981"      # Emerald green for clean audio & success
    ACCENT_CLEAN_HOVER = "#059669"
    ACCENT_GREEN = "#10B981"      # Green alias
    ACCENT_DIRTY = "#EF4444"      # Coral Red for original noisy audio
    ACCENT_DIRTY_HOVER = "#DC2626"
    ACCENT_RED = "#EF4444"        # Red alias
    ACCENT_CYAN = "#06B6D4"       # Cyan for playhead, progress, and interactive elements
    ACCENT_CYAN_HOVER = "#0891B2"
    ACCENT_AMBER = "#F59E0B"      # Warning/Caution state
    ACCENT_YELLOW = "#FBBF24"     # Yellow accent for cuts & highlights
    ACCENT_PURPLE = "#A78BFA"     # Purple accent for media split tools

    # Text & Typography
    TEXT_PRIMARY = "#F9FAFB"      # Crisp white for main headings
    TEXT_SECONDARY = "#9CA3AF"    # Muted gray for labels and metadata
    TEXT_MUTED = "#6B7280"        # Inactive or disabled text

    # Fonts
    FONT_FAMILY = "Segoe UI"      # Clean native Windows/cross-platform font
    FONT_TITLE = ("Segoe UI", 16, "bold")
    FONT_SUBTITLE = ("Segoe UI", 12, "bold")
    FONT_SUBHEADING = ("Segoe UI", 13, "bold")
    FONT_BODY = ("Segoe UI", 11)
    FONT_BODY_BOLD = ("Segoe UI", 11, "bold")
    FONT_SMALL = ("Segoe UI", 9)
    FONT_MONO = ("Consolas", 10)

    # Widget Styling Tokens
    CORNER_RADIUS_SM = 6
    CORNER_RADIUS_MD = 10
    CORNER_RADIUS_LG = 14


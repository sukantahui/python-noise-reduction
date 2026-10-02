"""UI component widgets for NoiseRelief Studio."""
from .drop_zone import DropZone
from .waveform_widget import WaveformWidget
from .player_controls import PlayerControls
from .settings_panel import SettingsPanel
from .batch_queue_view import BatchQueueView
from .about_dialog import AboutDialog
from .extract_dialog import ExtractAudioDialog

__all__ = [
    "DropZone",
    "WaveformWidget",
    "PlayerControls",
    "SettingsPanel",
    "BatchQueueView",
    "AboutDialog",
    "ExtractAudioDialog"
]


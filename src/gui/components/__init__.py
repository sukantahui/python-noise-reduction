"""UI component widgets for CNAT NOISERELIEF."""
from .drop_zone import DropZone
from .waveform_widget import WaveformWidget
from .player_controls import PlayerControls
from .settings_panel import SettingsPanel
from .batch_queue_view import BatchQueueView
from .about_dialog import AboutDialog
from .extract_dialog import ExtractAudioDialog
from .video_splitter_dialog import VideoSplitterDialog
from .audio_splitter_dialog import AudioSplitterDialog
from .selection_removal_dialog import SelectionRemovalDialog

__all__ = [
    "DropZone",
    "WaveformWidget",
    "PlayerControls",
    "SettingsPanel",
    "BatchQueueView",
    "AboutDialog",
    "ExtractAudioDialog",
    "VideoSplitterDialog",
    "AudioSplitterDialog",
    "SelectionRemovalDialog"
]


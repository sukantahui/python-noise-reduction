"""Audio file I/O, format conversion, and metadata inspection helpers."""
import os
import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from .logger import get_logger
from .ffmpeg_helper import FFmpegHelper
from .temp_manager import TempManager

logger = get_logger("AudioIO")


class AudioIO:
    """Handles audio loading, format conversion, saving, and metadata analysis."""

    @staticmethod
    def load_audio(file_path: Path | str, target_sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """Loads an audio file into a normalized float32 NumPy array and sample rate.

        Supports WAV, FLAC, OGG directly via soundfile, and automatically converts MP3/M4A/AAC/others
        via FFmpeg when necessary.

        Returns:
            Tuple of (audio_data, sample_rate) where audio_data has shape (samples,) for mono
            or (channels, samples) for multi-channel.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        try:
            # First try direct soundfile read
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)
            # data is shape (samples, channels), transpose to (channels, samples)
            audio_array = data.T
            if audio_array.shape[0] == 1:
                audio_array = audio_array.squeeze(0)  # Convert to 1D (samples,) for mono
            logger.info(f"Loaded audio {path.name}: sr={sr}, shape={audio_array.shape}, duration={audio_array.shape[-1]/sr:.2f}s")
            return audio_array, sr
        except Exception as direct_err:
            logger.debug(f"Direct soundfile read failed ({direct_err}), attempting FFmpeg extraction...")

            # Fallback: Convert via FFmpeg to a temporary 16-bit PCM WAV
            temp_wav = TempManager.create_temp_file(suffix=".wav")
            try:
                FFmpegHelper.extract_audio(
                    video_path=path,
                    output_wav_path=temp_wav,
                    sample_rate=target_sr or 48000,
                    channels=2
                )
                data, sr = sf.read(str(temp_wav), dtype="float32", always_2d=True)
                audio_array = data.T
                if audio_array.shape[0] == 1:
                    audio_array = audio_array.squeeze(0)
                logger.info(f"Loaded via FFmpeg conversion {path.name}: sr={sr}, shape={audio_array.shape}")
                return audio_array, sr
            finally:
                TempManager.remove_file(temp_wav)

    @staticmethod
    def save_audio(
        audio_array: np.ndarray,
        sample_rate: int,
        output_path: Path | str,
        subtype: Optional[str] = None
    ) -> Path:
        """Saves a NumPy audio array to disk in WAV, FLAC, OGG, or MP3 format.

        Args:
            audio_array: Shape (samples,) for mono or (channels, samples) for stereo, dtype float32.
            sample_rate: Audio sampling frequency in Hz.
            output_path: Destination file path.
            subtype: soundfile subtype (e.g., 'PCM_16', 'PCM_24', 'FLOAT').

        Returns:
            Path to saved file.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Transpose to (samples, channels) for soundfile if multi-channel
        if audio_array.ndim == 2:
            data_to_write = audio_array.T
        else:
            data_to_write = audio_array

        ext = out.suffix.lower()

        if ext in {".wav", ".flac", ".ogg"}:
            sf.write(str(out), data_to_write, sample_rate, subtype=subtype)
        elif ext == ".mp3":
            # Save temporary WAV and convert to MP3 with FFmpeg
            temp_wav = TempManager.create_temp_file(suffix=".wav")
            try:
                sf.write(str(temp_wav), data_to_write, sample_rate, subtype="PCM_16")
                ffmpeg_bin = FFmpegHelper.get_ffmpeg_path()
                cmd = [
                    ffmpeg_bin, "-y",
                    "-i", str(temp_wav),
                    "-codec:a", "libmp3lame",
                    "-b:a", "320k",
                    str(out)
                ]
                subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    check=True
                )
            finally:
                TempManager.remove_file(temp_wav)
        else:
            # Default to soundfile write
            sf.write(str(out), data_to_write, sample_rate)

        logger.info(f"Saved audio to: {out} ({out.stat().st_size} bytes)")
        return out

    @staticmethod
    def get_audio_metadata(file_path: Path | str) -> Dict[str, Any]:
        """Returns audio file metadata (duration, sample rate, channels, format)."""
        path = Path(file_path)
        try:
            info = sf.info(str(path))
            return {
                "name": path.name,
                "duration": info.duration,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype,
                "size_bytes": path.stat().st_size if path.exists() else 0
            }
        except Exception:
            # Fallback for video or non-SF files
            return {
                "name": path.name,
                "duration": 0.0,
                "sample_rate": 48000,
                "channels": 2,
                "format": path.suffix.upper().lstrip("."),
                "subtype": "Unknown",
                "size_bytes": path.stat().st_size if path.exists() else 0
            }

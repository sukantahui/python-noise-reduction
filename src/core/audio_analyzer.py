"""Audio signal analyzer for waveform envelope downsampling, RMS/Peak metering, and SNR calculation."""
import numpy as np
from typing import Tuple, Dict, Any
from src.utils.logger import get_logger

logger = get_logger("AudioAnalyzer")


class AudioAnalyzer:
    """Provides high-performance signal analysis and envelope extraction for UI visualization."""

    @staticmethod
    def downsample_waveform(audio: np.ndarray, num_bins: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
        """Downsamples full-length audio array to min/max envelopes for ultra-fast canvas rendering.

        Args:
            audio: Audio array of shape (samples,) or (channels, samples).
            num_bins: Number of horizontal pixel columns on the UI canvas (e.g. 800 - 1200).

        Returns:
            Tuple of (min_envelope, max_envelope), each of shape (num_bins,).
        """
        # If stereo/multi-channel, take mono downmix for display
        if audio.ndim > 1:
            mono = np.mean(audio, axis=0)
        else:
            mono = audio

        total_samples = len(mono)
        if total_samples <= num_bins:
            return mono, mono

        bin_size = total_samples // num_bins
        # Truncate to exact multiple of bin_size
        trimmed_len = bin_size * num_bins
        reshaped = mono[:trimmed_len].reshape(num_bins, bin_size)

        min_env = np.min(reshaped, axis=1)
        max_env = np.max(reshaped, axis=1)

        return min_env.astype(np.float32), max_env.astype(np.float32)

    @staticmethod
    def calculate_peak_dbfs(audio: np.ndarray) -> float:
        """Calculates peak level in dBFS."""
        peak = np.max(np.abs(audio))
        if peak < 1e-9:
            return -120.0
        return float(20.0 * np.log10(peak))

    @staticmethod
    def calculate_rms_dbfs(audio: np.ndarray) -> float:
        """Calculates Root-Mean-Square (RMS) energy level in dBFS."""
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 1e-9:
            return -120.0
        return float(20.0 * np.log10(rms))

    @staticmethod
    def estimate_snr_db(noisy_audio: np.ndarray, clean_audio: np.ndarray) -> float:
        """Estimates empirical Signal-to-Noise Ratio (SNR) improvement in dB.

        Args:
            noisy_audio: Original input array with noise.
            clean_audio: Processed denoised array.

        Returns:
            Estimated SNR value in dB.
        """
        # Ensure identical shape
        min_len = min(noisy_audio.shape[-1], clean_audio.shape[-1])
        n_slice = noisy_audio[..., :min_len]
        c_slice = clean_audio[..., :min_len]

        signal_power = np.mean(c_slice ** 2)
        noise_residual = n_slice - c_slice
        noise_power = np.mean(noise_residual ** 2)

        if noise_power < 1e-12:
            return 45.0  # Cap at high clean SNR
        if signal_power < 1e-12:
            return 0.0

        snr = 10.0 * np.log10(signal_power / noise_power)
        return float(np.clip(snr, 0.0, 60.0))

    @staticmethod
    def estimate_noise_floor_dbfs(audio: np.ndarray, frame_size: int = 2048) -> float:
        """Estimates ambient noise floor level in dBFS using 10th percentile energy window."""
        if audio.ndim > 1:
            mono = np.mean(audio, axis=0)
        else:
            mono = audio

        num_frames = len(mono) // frame_size
        if num_frames < 2:
            return AudioAnalyzer.calculate_rms_dbfs(mono)

        frames = mono[: num_frames * frame_size].reshape(num_frames, frame_size)
        frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
        # 10th percentile lowest energy frames represent noise floor
        noise_floor_rms = np.percentile(frame_rms, 10)

        if noise_floor_rms < 1e-9:
            return -120.0
        return float(20.0 * np.log10(noise_floor_rms))

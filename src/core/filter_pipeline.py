"""Audio filter pipeline providing zero-phase high-pass, low-pass, notch, noise gate, and normalization."""
import numpy as np
from scipy import signal
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger("FilterPipeline")


class FilterPipeline:
    """Zero-phase digital signal processing filter collection for audio pre/post-processing."""

    @staticmethod
    def high_pass(
        audio: np.ndarray,
        sample_rate: int,
        cutoff_hz: float = 80.0,
        order: int = 4
    ) -> np.ndarray:
        """Applies zero-phase Butterworth high-pass filter to eliminate sub-bass rumble and DC bias.

        Args:
            audio: Audio array of shape (samples,) or (channels, samples).
            sample_rate: Audio sampling rate in Hz.
            cutoff_hz: High-pass frequency cutoff in Hz (e.g., 80Hz).
            order: Filter order (default 4).

        Returns:
            Filtered audio array with identical shape and dtype.
        """
        if cutoff_hz <= 0 or cutoff_hz >= (sample_rate / 2.0):
            return audio

        nyquist = 0.5 * sample_rate
        norm_cutoff = min(max(cutoff_hz / nyquist, 0.001), 0.999)
        sos = signal.butter(order, norm_cutoff, btype="highpass", output="sos")

        if audio.ndim == 1:
            filtered = signal.sosfiltfilt(sos, audio)
        else:
            filtered = np.zeros_like(audio)
            for ch in range(audio.shape[0]):
                filtered[ch] = signal.sosfiltfilt(sos, audio[ch])

        return filtered.astype(np.float32)

    @staticmethod
    def low_pass(
        audio: np.ndarray,
        sample_rate: int,
        cutoff_hz: float = 16000.0,
        order: int = 4
    ) -> np.ndarray:
        """Applies zero-phase Butterworth low-pass filter to eliminate high-frequency tape/mic hiss.

        Args:
            audio: Audio array of shape (samples,) or (channels, samples).
            sample_rate: Audio sampling rate in Hz.
            cutoff_hz: Low-pass frequency cutoff in Hz.
            order: Filter order (default 4).

        Returns:
            Filtered audio array with identical shape and dtype.
        """
        if cutoff_hz <= 0 or cutoff_hz >= (sample_rate / 2.0):
            return audio

        nyquist = 0.5 * sample_rate
        norm_cutoff = min(max(cutoff_hz / nyquist, 0.001), 0.999)
        sos = signal.butter(order, norm_cutoff, btype="lowpass", output="sos")

        if audio.ndim == 1:
            filtered = signal.sosfiltfilt(sos, audio)
        else:
            filtered = np.zeros_like(audio)
            for ch in range(audio.shape[0]):
                filtered[ch] = signal.sosfiltfilt(sos, audio[ch])

        return filtered.astype(np.float32)

    @staticmethod
    def notch(
        audio: np.ndarray,
        sample_rate: int,
        notch_freq_hz: float = 50.0,
        quality_factor: float = 30.0
    ) -> np.ndarray:
        """Applies a zero-phase IIR notch filter to remove specific electrical mains hum (50Hz or 60Hz)."""
        if notch_freq_hz <= 0 or notch_freq_hz >= (sample_rate / 2.0):
            return audio

        b, a = signal.iirnotch(notch_freq_hz, quality_factor, fs=sample_rate)

        if audio.ndim == 1:
            filtered = signal.filtfilt(b, a, audio)
        else:
            filtered = np.zeros_like(audio)
            for ch in range(audio.shape[0]):
                filtered[ch] = signal.filtfilt(b, a, audio[ch])

        return filtered.astype(np.float32)

    @staticmethod
    def noise_gate(
        audio: np.ndarray,
        threshold_db: float = -45.0,
        ratio: float = 4.0,
        attack_ms: float = 10.0,
        release_ms: float = 80.0,
        sample_rate: int = 48000
    ) -> np.ndarray:
        """Applies a smooth soft-knee downward expander / noise gate to silence pause intervals.

        Args:
            audio: Audio array of shape (samples,) or (channels, samples).
            threshold_db: Gate threshold in dBFS (e.g. -45 dB).
            ratio: Expansion ratio (e.g. 4.0).
            attack_ms: Attack time in milliseconds.
            release_ms: Release time in milliseconds.
            sample_rate: Sampling frequency.
        """
        if threshold_db <= -90.0:
            return audio  # Gate effectively disabled

        threshold_lin = 10.0 ** (threshold_db / 20.0)
        attack_coef = np.exp(-1.0 / (sample_rate * (attack_ms / 1000.0)))
        release_coef = np.exp(-1.0 / (sample_rate * (release_ms / 1000.0)))

        def _process_channel(x: np.ndarray) -> np.ndarray:
            abs_x = np.abs(x)
            envelope = np.zeros_like(abs_x)
            env = 0.0

            for i in range(len(abs_x)):
                val = abs_x[i]
                if val > env:
                    env = attack_coef * env + (1.0 - attack_coef) * val
                else:
                    env = release_coef * env + (1.0 - release_coef) * val
                envelope[i] = env

            # Compute gain reduction
            eps = 1e-12
            env_db = 20.0 * np.log10(np.maximum(envelope, eps))
            gain_db = np.zeros_like(env_db)
            below_idx = env_db < threshold_db
            gain_db[below_idx] = (env_db[below_idx] - threshold_db) * (1.0 - 1.0 / ratio)
            gain_lin = 10.0 ** (gain_db / 20.0)

            return x * gain_lin

        if audio.ndim == 1:
            out = _process_channel(audio)
        else:
            out = np.zeros_like(audio)
            for ch in range(audio.shape[0]):
                out[ch] = _process_channel(audio[ch])

        return out.astype(np.float32)

    @staticmethod
    def peak_normalize(
        audio: np.ndarray,
        target_dbfs: float = -1.0
    ) -> np.ndarray:
        """Normalizes audio to a specified peak dBFS level (e.g. -1.0 dBFS)."""
        peak = np.max(np.abs(audio))
        if peak < 1e-9:
            return audio

        target_peak = 10.0 ** (target_dbfs / 20.0)
        scale = target_peak / peak
        return (audio * scale).astype(np.float32)

    @staticmethod
    def soft_limiter(
        audio: np.ndarray,
        threshold_dbfs: float = -0.5
    ) -> np.ndarray:
        """Applies soft-knee saturation limiter to prevent digital hard clipping."""
        thresh = 10.0 ** (threshold_dbfs / 20.0)
        out = np.copy(audio)
        mask = np.abs(out) > thresh
        # Soft sigmoid compression for over-threshold samples
        out[mask] = np.sign(out[mask]) * (thresh + (1.0 - thresh) * np.tanh((np.abs(out[mask]) - thresh) / (1.0 - thresh + 1e-9)))
        return out.astype(np.float32)

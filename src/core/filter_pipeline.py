"""Audio filter pipeline providing zero-phase high-pass, low-pass, notch, noise gate, EQ, and normalization."""
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
        """Applies zero-phase Butterworth high-pass filter to eliminate sub-bass rumble and DC bias."""
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
        """Applies zero-phase Butterworth low-pass filter to eliminate high-frequency tape/mic hiss."""
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
    def de_hum_harmonics(
        audio: np.ndarray,
        sample_rate: int,
        base_freq_hz: float = 50.0,
        num_harmonics: int = 4,
        quality_factor: float = 30.0
    ) -> np.ndarray:
        """Removes electrical fundamental hum and its integer harmonic overtones (e.g. 50, 100, 150, 200 Hz)."""
        out = audio
        nyquist = 0.5 * sample_rate
        for h in range(1, num_harmonics + 1):
            freq = base_freq_hz * h
            if freq < nyquist - 50:
                out = FilterPipeline.notch(out, sample_rate, notch_freq_hz=freq, quality_factor=quality_factor)
        return out

    @staticmethod
    def parametric_eq(
        audio: np.ndarray,
        sample_rate: int,
        center_freq_hz: float = 3200.0,
        gain_db: float = 3.0,
        q: float = 1.0
    ) -> np.ndarray:
        """Applies second-order parametric peaking/bell filter for vocal presence or targeted frequency shaping."""
        if abs(gain_db) < 0.1 or center_freq_hz <= 20 or center_freq_hz >= (sample_rate / 2.0 - 100):
            return audio

        A = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * np.pi * center_freq_hz / sample_rate
        alpha = np.sin(w0) / (2.0 * q)

        b0 = 1.0 + alpha * A
        b1 = -2.0 * np.cos(w0)
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * np.cos(w0)
        a2 = 1.0 - alpha / A

        b = np.array([b0 / a0, b1 / a0, b2 / a0], dtype=np.float64)
        a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float64)

        if audio.ndim == 1:
            filtered = signal.filtfilt(b, a, audio)
        else:
            filtered = np.zeros_like(audio)
            for ch in range(audio.shape[0]):
                filtered[ch] = signal.filtfilt(b, a, audio[ch])

        return filtered.astype(np.float32)

    @staticmethod
    def voice_presence_boost(
        audio: np.ndarray,
        sample_rate: int,
        gain_db: float = 3.0,
        freq_hz: float = 3400.0
    ) -> np.ndarray:
        """Enhances speech clarity and voice intelligibility in the 3.4 kHz presence band."""
        return FilterPipeline.parametric_eq(audio, sample_rate, center_freq_hz=freq_hz, gain_db=gain_db, q=1.2)

    @staticmethod
    def noise_gate(
        audio: np.ndarray,
        threshold_db: float = -45.0,
        ratio: float = 4.0,
        attack_ms: float = 10.0,
        release_ms: float = 80.0,
        sample_rate: int = 48000
    ) -> np.ndarray:
        """High-performance vectorized soft-knee downward expander / noise gate to silence pause intervals."""
        if threshold_db <= -85.0:
            return audio  # Gate effectively disabled

        # Hop size for block envelope detection (e.g. 64 samples = ~1.3ms at 48kHz)
        hop_size = 64
        num_samples = audio.shape[-1]
        if num_samples < hop_size * 2:
            return audio

        attack_coef = np.exp(-hop_size / (sample_rate * (attack_ms / 1000.0)))
        release_coef = np.exp(-hop_size / (sample_rate * (release_ms / 1000.0)))

        def _process_channel(x: np.ndarray) -> np.ndarray:
            # Block RMS / Peak calculation
            num_blocks = len(x) // hop_size
            trimmed = x[: num_blocks * hop_size].reshape(num_blocks, hop_size)
            block_peaks = np.max(np.abs(trimmed), axis=1)

            # Recursive envelope smoothing over downsampled blocks (ultra-fast)
            envelope = np.zeros(num_blocks, dtype=np.float32)
            env = 0.0
            for i in range(num_blocks):
                val = block_peaks[i]
                if val > env:
                    env = attack_coef * env + (1.0 - attack_coef) * val
                else:
                    env = release_coef * env + (1.0 - release_coef) * val
                envelope[i] = env

            # Compute gain reduction in dB
            eps = 1e-12
            env_db = 20.0 * np.log10(np.maximum(envelope, eps))
            gain_db = np.zeros_like(env_db)
            below_idx = env_db < threshold_db
            gain_db[below_idx] = (env_db[below_idx] - threshold_db) * (1.0 - 1.0 / ratio)
            gain_lin_blocks = 10.0 ** (gain_db / 20.0)

            # Interpolate smoothly back to full sample resolution
            block_indices = np.linspace(0, len(x) - 1, num_blocks)
            full_indices = np.arange(len(x))
            gain_lin = np.interp(full_indices, block_indices, gain_lin_blocks).astype(np.float32)

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

"""Core Audio Denoising Engine implementing spectral gating, adaptive filtering, and DSP processing."""
import numpy as np
import noisereduce as nr
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from .filter_pipeline import FilterPipeline
from src.utils.logger import get_logger

logger = get_logger("AudioEngine")


@dataclass
class DenoiseConfig:
    """Configuration parameter set for audio noise reduction."""
    reduction_strength: float = 0.80       # 0.1 to 1.0 (proportion of noise reduced)
    stationary_mode: bool = True           # True: constant noise (fans, hiss); False: dynamic (wind, streets)
    high_pass_hz: float = 80.0             # High-pass filter cutoff (0 to disable)
    low_pass_hz: float = 0.0               # Low-pass filter cutoff (0 to disable)
    notch_50hz: bool = False               # 50Hz electrical hum notch filter
    notch_60hz: bool = False               # 60Hz electrical hum notch filter
    time_smoothing: int = 3                # STFT time mask smoothing (1 to 10)
    noise_gate_db: float = -50.0           # Soft noise gate threshold in dBFS (0 to disable)
    normalize: bool = True                 # Peak normalize output to -1.0 dBFS
    chunk_size_sec: float = 30.0           # Chunk size in seconds for memory efficiency on long tracks


class AudioDenoiseEngine:
    """High-performance audio noise suppression engine using spectral gating and DSP filters."""

    # Standard Presets
    PRESETS: Dict[str, DenoiseConfig] = {
        "Default Studio Voice": DenoiseConfig(
            reduction_strength=0.80,
            stationary_mode=True,
            high_pass_hz=80.0,
            low_pass_hz=0.0,
            time_smoothing=3,
            noise_gate_db=-48.0,
            normalize=True
        ),
        "Mild Background Hiss": DenoiseConfig(
            reduction_strength=0.55,
            stationary_mode=True,
            high_pass_hz=40.0,
            low_pass_hz=0.0,
            time_smoothing=2,
            noise_gate_db=-60.0,
            normalize=True
        ),
        "Aggressive Fan / Air Conditioner": DenoiseConfig(
            reduction_strength=0.95,
            stationary_mode=True,
            high_pass_hz=100.0,
            low_pass_hz=0.0,
            time_smoothing=4,
            noise_gate_db=-42.0,
            normalize=True
        ),
        "Outdoor Wind & Street Noise": DenoiseConfig(
            reduction_strength=0.85,
            stationary_mode=False,
            high_pass_hz=120.0,
            low_pass_hz=15000.0,
            time_smoothing=4,
            noise_gate_db=-45.0,
            normalize=True
        ),
        "Vintage Tape & Vinyl Restore": DenoiseConfig(
            reduction_strength=0.75,
            stationary_mode=True,
            high_pass_hz=50.0,
            low_pass_hz=14000.0,
            time_smoothing=3,
            noise_gate_db=-55.0,
            normalize=True
        ),
    }

    @classmethod
    def get_preset(cls, name: str) -> DenoiseConfig:
        """Returns a copy of a preset configuration."""
        if name in cls.PRESETS:
            p = cls.PRESETS[name]
            return DenoiseConfig(**p.__dict__)
        return DenoiseConfig()

    @classmethod
    def process_audio(
        cls,
        audio: np.ndarray,
        sample_rate: int,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> np.ndarray:
        """Executes full denoising pipeline on audio array.

        Args:
            audio: Input audio array of shape (samples,) or (channels, samples), float32.
            sample_rate: Sampling frequency in Hz.
            config: DenoiseConfig parameter object.
            progress_callback: Optional callback func(percent: float, message: str).

        Returns:
            Denoised audio array of identical shape, float32.
        """
        if config is None:
            config = DenoiseConfig()

        if progress_callback:
            progress_callback(5.0, "Pre-filtering signal...")

        out = np.copy(audio)

        # 1. Pre-filter: High-pass
        if config.high_pass_hz > 0:
            out = FilterPipeline.high_pass(out, sample_rate, cutoff_hz=config.high_pass_hz)

        # 2. Notch filters for 50Hz / 60Hz hum if enabled
        if config.notch_50hz:
            out = FilterPipeline.notch(out, sample_rate, notch_freq_hz=50.0)
        if config.notch_60hz:
            out = FilterPipeline.notch(out, sample_rate, notch_freq_hz=60.0)

        if progress_callback:
            progress_callback(20.0, "Applying spectral gating noise reduction...")

        # 3. Spectral Gating Noise Reduction
        # noisereduce expects 1D or (channels, samples)
        prop_decrease = float(np.clip(config.reduction_strength, 0.05, 1.0))
        time_mask_smooth_ms = int(config.time_smoothing * 15)  # Convert frame count to ms

        try:
            if config.stationary_mode:
                denoised = nr.reduce_noise(
                    y=out,
                    sr=sample_rate,
                    prop_decrease=prop_decrease,
                    stationary=True,
                    time_mask_smooth_ms=time_mask_smooth_ms,
                    n_jobs=-1
                )
            else:
                denoised = nr.reduce_noise(
                    y=out,
                    sr=sample_rate,
                    prop_decrease=prop_decrease,
                    stationary=False,
                    time_mask_smooth_ms=time_mask_smooth_ms,
                    n_jobs=-1
                )
        except Exception as ex:
            logger.error(f"noisereduce failed ({ex}), falling back to direct filtering.")
            denoised = out

        if progress_callback:
            progress_callback(75.0, "Applying post-processing filters...")

        # 4. Low-pass filter if configured
        if config.low_pass_hz > 0:
            denoised = FilterPipeline.low_pass(denoised, sample_rate, cutoff_hz=config.low_pass_hz)

        # 5. Soft noise gate
        if config.noise_gate_db > -80.0:
            denoised = FilterPipeline.noise_gate(
                denoised,
                threshold_db=config.noise_gate_db,
                sample_rate=sample_rate
            )

        # 6. Peak Normalization & Limiter
        if config.normalize:
            denoised = FilterPipeline.peak_normalize(denoised, target_dbfs=-1.0)
        denoised = FilterPipeline.soft_limiter(denoised, threshold_dbfs=-0.3)

        if progress_callback:
            progress_callback(100.0, "Denoising complete.")

        return denoised.astype(np.float32)

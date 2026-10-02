"""Core Audio Denoising Engine implementing spectral gating, adaptive filtering, noise profiling, and DSP processing."""
import numpy as np
import noisereduce as nr
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, Tuple
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
    de_hum_harmonics: bool = False         # Cut 50/60Hz harmonic overtones
    voice_clarity_boost: bool = False      # Speech presence & intelligibility enhancer
    voice_boost_db: float = 3.0            # Voice boost gain in dB (1.0 to 6.0)
    auto_noise_profile: bool = True        # Automatically extract quietest window as noise fingerprint
    time_smoothing: int = 3                # STFT time mask smoothing (1 to 10)
    noise_gate_db: float = -50.0           # Soft noise gate threshold in dBFS (0 or <=-85 to disable)
    normalize: bool = True                 # Peak normalize output to -1.0 dBFS
    chunk_size_sec: float = 45.0           # Chunk size in seconds for memory efficiency on long tracks


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
            voice_clarity_boost=True,
            voice_boost_db=2.5,
            auto_noise_profile=True,
            normalize=True
        ),
        "Podcast & Voice Clarity": DenoiseConfig(
            reduction_strength=0.85,
            stationary_mode=True,
            high_pass_hz=85.0,
            low_pass_hz=16000.0,
            time_smoothing=3,
            noise_gate_db=-46.0,
            voice_clarity_boost=True,
            voice_boost_db=4.0,
            auto_noise_profile=True,
            normalize=True
        ),
        "Mild Background Hiss": DenoiseConfig(
            reduction_strength=0.55,
            stationary_mode=True,
            high_pass_hz=40.0,
            low_pass_hz=0.0,
            time_smoothing=2,
            noise_gate_db=-60.0,
            voice_clarity_boost=False,
            auto_noise_profile=True,
            normalize=True
        ),
        "Aggressive Fan / Air Conditioner": DenoiseConfig(
            reduction_strength=0.95,
            stationary_mode=True,
            high_pass_hz=100.0,
            low_pass_hz=0.0,
            time_smoothing=4,
            noise_gate_db=-42.0,
            voice_clarity_boost=True,
            voice_boost_db=3.0,
            auto_noise_profile=True,
            normalize=True
        ),
        "Outdoor Wind & Street Noise": DenoiseConfig(
            reduction_strength=0.85,
            stationary_mode=False,
            high_pass_hz=120.0,
            low_pass_hz=14500.0,
            time_smoothing=4,
            noise_gate_db=-45.0,
            voice_clarity_boost=True,
            voice_boost_db=3.5,
            auto_noise_profile=False,
            normalize=True
        ),
        "Electrical De-Hum Studio": DenoiseConfig(
            reduction_strength=0.75,
            stationary_mode=True,
            high_pass_hz=50.0,
            low_pass_hz=0.0,
            notch_50hz=True,
            de_hum_harmonics=True,
            time_smoothing=3,
            noise_gate_db=-52.0,
            auto_noise_profile=True,
            normalize=True
        ),
        "Vintage Tape & Vinyl Restore": DenoiseConfig(
            reduction_strength=0.75,
            stationary_mode=True,
            high_pass_hz=50.0,
            low_pass_hz=14000.0,
            time_smoothing=3,
            noise_gate_db=-55.0,
            auto_noise_profile=True,
            normalize=True
        ),
        "Gentle Mastering Denoise": DenoiseConfig(
            reduction_strength=0.45,
            stationary_mode=True,
            high_pass_hz=30.0,
            low_pass_hz=0.0,
            time_smoothing=2,
            noise_gate_db=-65.0,
            voice_clarity_boost=False,
            auto_noise_profile=True,
            normalize=False
        ),
    }

    @classmethod
    def get_preset(cls, name: str) -> DenoiseConfig:
        """Returns a copy of a preset configuration."""
        if name in cls.PRESETS:
            p = cls.PRESETS[name]
            return DenoiseConfig(**p.__dict__)
        return DenoiseConfig()

    @staticmethod
    def extract_noise_profile(
        audio: np.ndarray,
        sample_rate: int,
        duration_sec: float = 0.5
    ) -> Optional[np.ndarray]:
        """Finds the lowest RMS energy segment in the audio track to use as stationary noise profile."""
        window_len = int(sample_rate * duration_sec)
        total_samples = audio.shape[-1]
        if total_samples < window_len * 2:
            return None

        # Work on mono downmix to find minimum energy window
        mono = np.mean(audio, axis=0) if audio.ndim > 1 else audio
        hop = window_len // 2
        num_windows = (len(mono) - window_len) // hop

        if num_windows < 1:
            return None

        min_energy = float("inf")
        best_idx = 0

        for i in range(num_windows):
            start = i * hop
            segment = mono[start : start + window_len]
            energy = np.sum(segment ** 2)
            if energy < min_energy:
                min_energy = energy
                best_idx = start

        if audio.ndim == 1:
            return audio[best_idx : best_idx + window_len]
        else:
            return audio[:, best_idx : best_idx + window_len]

    @classmethod
    def process_audio(
        cls,
        audio: np.ndarray,
        sample_rate: int,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> np.ndarray:
        """Executes full denoising pipeline on audio array."""
        if config is None:
            config = DenoiseConfig()

        if progress_callback:
            progress_callback(5.0, "Pre-filtering signal (High-pass / De-hum)...")

        out = np.copy(audio)

        # 1. Pre-filter: High-pass
        if config.high_pass_hz > 0:
            out = FilterPipeline.high_pass(out, sample_rate, cutoff_hz=config.high_pass_hz)

        # 2. Notch & Harmonic De-Humming
        if config.de_hum_harmonics:
            base = 50.0 if config.notch_50hz or not config.notch_60hz else 60.0
            out = FilterPipeline.de_hum_harmonics(out, sample_rate, base_freq_hz=base, num_harmonics=4)
        else:
            if config.notch_50hz:
                out = FilterPipeline.notch(out, sample_rate, notch_freq_hz=50.0)
            if config.notch_60hz:
                out = FilterPipeline.notch(out, sample_rate, notch_freq_hz=60.0)

        # 3. Noise Profile extraction
        y_noise = None
        if config.stationary_mode and config.auto_noise_profile:
            y_noise = cls.extract_noise_profile(out, sample_rate, duration_sec=0.6)

        if progress_callback:
            progress_callback(25.0, "Executing spectral gating noise reduction...")

        # 4. Spectral Gating Noise Reduction
        prop_decrease = float(np.clip(config.reduction_strength, 0.05, 1.0))
        time_mask_smooth_ms = int(config.time_smoothing * 15)

        try:
            if config.stationary_mode:
                if y_noise is not None:
                    denoised = nr.reduce_noise(
                        y=out,
                        sr=sample_rate,
                        y_noise=y_noise,
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
            logger.error(f"Spectral gating failed ({ex}), fallback to filtered output.")
            denoised = out

        if progress_callback:
            progress_callback(70.0, "Applying voice presence and post-filters...")

        # 5. Voice Presence / Clarity Enhancer
        if config.voice_clarity_boost:
            denoised = FilterPipeline.voice_presence_boost(
                denoised,
                sample_rate,
                gain_db=config.voice_boost_db,
                freq_hz=3400.0
            )

        # 6. Low-pass filter if configured
        if config.low_pass_hz > 0:
            denoised = FilterPipeline.low_pass(denoised, sample_rate, cutoff_hz=config.low_pass_hz)

        # 7. Soft noise gate
        if config.noise_gate_db > -85.0:
            denoised = FilterPipeline.noise_gate(
                denoised,
                threshold_db=config.noise_gate_db,
                sample_rate=sample_rate
            )

        # 8. Peak Normalization & Limiter
        if config.normalize:
            denoised = FilterPipeline.peak_normalize(denoised, target_dbfs=-1.0)
        denoised = FilterPipeline.soft_limiter(denoised, threshold_dbfs=-0.3)

        if progress_callback:
            progress_callback(100.0, "Denoising complete.")

        return denoised.astype(np.float32)

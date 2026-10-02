"""Core Audio Denoising Engine implementing spectral gating, adaptive filtering, noise profiling, and DSP processing."""
import numpy as np
import noisereduce as nr
from pathlib import Path
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

    @classmethod
    def trim_audio_range(
        cls,
        audio_path: Path | str,
        start_sec: float,
        end_sec: float,
        output_path: Path | str,
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Path:
        """Extracts and saves a time slice [start_sec, end_sec] from an audio track with optional denoising."""
        from src.utils.audio_io import AudioIO

        a_path = Path(audio_path)
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(20.0, f"Loading audio track slice ({start_sec:.1f}s - {end_sec:.1f}s)...")

        audio_arr, sr = AudioIO.load_audio(a_path)
        total_len = audio_arr.shape[-1]
        start_idx = max(0, int(start_sec * sr))
        end_idx = min(total_len, int(end_sec * sr)) if end_sec > start_sec else total_len

        sliced = audio_arr[..., start_idx:end_idx]

        if denoise:
            if progress_callback:
                progress_callback(50.0, "Applying noise reduction to sliced audio...")
            sliced = cls.process_audio(sliced, sample_rate=sr, config=config)

        if progress_callback:
            progress_callback(85.0, f"Saving sliced audio to {out_path.name}...")

        AudioIO.save_audio(sliced, sample_rate=sr, output_path=out_path)

        if progress_callback:
            progress_callback(100.0, f"Saved: {out_path.name}")
        return out_path

    @classmethod
    def split_audio_by_duration(
        cls,
        audio_path: Path | str,
        segment_duration_sec: float,
        output_dir: Path | str,
        output_format: str = "wav",
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> list[Path]:
        """Splits an audio file into fixed-duration segments."""
        from src.utils.audio_io import AudioIO

        a_path = Path(audio_path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        audio_arr, sr = AudioIO.load_audio(a_path)
        total_samples = audio_arr.shape[-1]
        total_duration = total_samples / float(sr)

        seg_samples = int(max(0.5, segment_duration_sec) * sr)
        num_segments = int(total_samples // seg_samples)
        if total_samples % seg_samples > int(0.1 * sr):
            num_segments += 1

        output_files: list[Path] = []
        stem = a_path.stem
        ext = f".{output_format.lower().lstrip('.')}"

        for i in range(num_segments):
            start = i * seg_samples
            end = min(total_samples, start + seg_samples)
            if (end - start) < int(0.1 * sr):
                continue

            chunk = audio_arr[..., start:end]
            if denoise:
                chunk = cls.process_audio(chunk, sample_rate=sr, config=config)

            part_name = f"{stem}_part{i+1:03d}{ext}"
            part_path = out_dir / part_name

            if progress_callback:
                pct = (i / num_segments) * 100.0
                progress_callback(pct, f"Exporting audio segment {i+1}/{num_segments}...")

            AudioIO.save_audio(chunk, sample_rate=sr, output_path=part_path)
            output_files.append(part_path)

        if progress_callback:
            progress_callback(100.0, f"Successfully created {len(output_files)} audio segments.")
        return output_files

    @classmethod
    def split_audio_by_parts(
        cls,
        audio_path: Path | str,
        num_parts: int,
        output_dir: Path | str,
        output_format: str = "wav",
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> list[Path]:
        """Splits an audio file into N equal parts."""
        from src.utils.audio_io import AudioIO

        a_path = Path(audio_path)
        audio_arr, sr = AudioIO.load_audio(a_path)
        total_duration = audio_arr.shape[-1] / float(sr)

        num_parts = max(2, min(50, num_parts))
        seg_duration = total_duration / float(num_parts)

        return cls.split_audio_by_duration(
            audio_path=audio_path,
            segment_duration_sec=seg_duration,
            output_dir=output_dir,
            output_format=output_format,
            denoise=denoise,
            config=config,
            progress_callback=progress_callback
        )

    @classmethod
    def split_audio_by_silence(
        cls,
        audio_path: Path | str,
        output_dir: Path | str,
        min_silence_len_sec: float = 0.8,
        silence_threshold_db: float = -38.0,
        output_format: str = "wav",
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> list[Path]:
        """Automatically splits an audio recording at silent pause intervals into separate takes/clips."""
        from src.utils.audio_io import AudioIO

        a_path = Path(audio_path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(10.0, "Analyzing audio track for silent pause intervals...")

        audio_arr, sr = AudioIO.load_audio(a_path)
        mono = np.mean(audio_arr, axis=0) if audio_arr.ndim > 1 else audio_arr
        total_samples = len(mono)

        frame_len = int(0.05 * sr)  # 50ms frames
        hop_len = int(0.025 * sr)   # 25ms hop
        num_frames = max(1, (total_samples - frame_len) // hop_len)

        # Calculate frame energies in dBFS
        frame_indices = np.arange(num_frames) * hop_len
        is_silent = np.zeros(num_frames, dtype=bool)

        for i, idx in enumerate(frame_indices):
            segment = mono[idx : idx + frame_len]
            rms = np.sqrt(np.mean(segment ** 2))
            db = 20.0 * np.log10(max(rms, 1e-9))
            is_silent[i] = db < silence_threshold_db

        # Find continuous silence blocks >= min_silence_len_sec
        min_silent_frames = int(min_silence_len_sec / 0.025)
        split_points = [0]
        cur_silent_count = 0
        silence_start_frame = 0

        for i in range(num_frames):
            if is_silent[i]:
                if cur_silent_count == 0:
                    silence_start_frame = i
                cur_silent_count += 1
            else:
                if cur_silent_count >= min_silent_frames:
                    # Split in the middle of silence
                    mid_frame = (silence_start_frame + i) // 2
                    mid_sample = frame_indices[mid_frame]
                    # Only add if sufficiently far from last split (> 1s)
                    if (mid_sample - split_points[-1]) > int(1.0 * sr):
                        split_points.append(mid_sample)
                cur_silent_count = 0

        split_points.append(total_samples)

        output_files: list[Path] = []
        stem = a_path.stem
        ext = f".{output_format.lower().lstrip('.')}"
        num_clips = len(split_points) - 1

        for i in range(num_clips):
            s = split_points[i]
            e = split_points[i + 1]
            if (e - s) < int(0.5 * sr):
                continue

            chunk = audio_arr[..., s:e]
            if denoise:
                chunk = cls.process_audio(chunk, sample_rate=sr, config=config)

            part_name = f"{stem}_clip{i+1:03d}{ext}"
            part_path = out_dir / part_name

            if progress_callback:
                pct = 30.0 + (i / num_clips) * 65.0
                progress_callback(pct, f"Saving silence-split take {i+1}/{num_clips}...")

            AudioIO.save_audio(chunk, sample_rate=sr, output_path=part_path)
            output_files.append(part_path)

        if progress_callback:
            progress_callback(100.0, f"Successfully split into {len(output_files)} audio takes.")
        return output_files

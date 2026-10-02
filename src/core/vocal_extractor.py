"""High-performance Vocal Isolation and Instrumental/Karaoke Separation DSP Engine."""
import numpy as np
import scipy.signal as signal
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Tuple
import soundfile as sf

from src.utils.audio_io import AudioIO
from src.core.filter_pipeline import FilterPipeline
from src.utils.logger import get_logger

logger = get_logger("VocalExtractor")


@dataclass
class VocalExtractionConfig:
    """Configuration parameter set for vocal isolation and accompaniment separation."""
    vocal_sensitivity: float = 0.85       # 0.5 to 1.0 (Center channel isolation aggression)
    vocal_low_cutoff_hz: float = 100.0    # Suppress low bass/kick below this frequency
    vocal_high_cutoff_hz: float = 8500.0  # Suppress high cymbals/hiss above this frequency
    stereo_cancellation_strength: float = 1.0  # 0.0 to 1.5 (strength of side cancellation)
    enhance_speech_formants: bool = True  # Boost voice intelligibility (2.5 - 4.0 kHz)
    spectral_smoothing: int = 3           # STFT time-frequency mask smoothing
    remove_drums_bass: bool = True        # High-pass and notch filtering for drum/bass isolation
    normalize_output: bool = True         # Peak normalize output track


class VocalExtractor:
    """Isolates vocals (Acapella) and extracts accompaniments (Instrumental) from audio tracks."""

    @classmethod
    def separate_audio(
        cls,
        audio_arr: np.ndarray,
        sample_rate: int,
        config: Optional[VocalExtractionConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Separates an input audio array into (vocals_arr, instrumental_arr).

        Args:
            audio_arr: Input audio array (shape: (channels, samples) or (samples,)).
            sample_rate: Audio sampling frequency in Hz.
            config: Vocal extraction configuration.
            progress_callback: Callback reporting progress (0-100%).

        Returns:
            Tuple of (vocals_audio, instrumental_audio) as float32 numpy arrays.
        """
        cfg = config or VocalExtractionConfig()
        audio = audio_arr.astype(np.float32)

        is_stereo = audio.ndim > 1 and audio.shape[0] >= 2
        total_samples = audio.shape[-1]

        if progress_callback:
            progress_callback(15.0, "Analyzing stereo center image and frequency spectrum...")

        if is_stereo:
            left = audio[0]
            right = audio[1]

            # Mid (Center) and Side (Stereo Width) Decomposition
            # Vocals are predominantly panned in the center (M), while stereo instruments are in S
            mid = (left + right) * 0.5
            side = (left - right) * 0.5

            # STFT Analysis
            n_fft = 2048
            hop_length = 512
            win = np.hanning(n_fft)

            _, _, zxx_l = signal.stft(left, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
            _, _, zxx_r = signal.stft(right, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
            f_bins, t_frames, zxx_m = signal.stft(mid, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
            _, _, zxx_s = signal.stft(side, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)

            if progress_callback:
                progress_callback(35.0, "Computing spectral pan-coherence and vocal presence masks...")

            # Spectral Coherence & Center Extraction Mask
            mag_l = np.abs(zxx_l)
            mag_r = np.abs(zxx_r)
            mag_m = np.abs(zxx_m)
            mag_s = np.abs(zxx_s)

            # Center similarity metric: high when Left == Right (Center Vocal), low when panned
            pan_similarity = 2.0 * (mag_l * mag_r) / (mag_l**2 + mag_r**2 + 1e-8)
            center_mask = np.power(np.clip(pan_similarity, 0.0, 1.0), 1.0 / max(0.1, cfg.vocal_sensitivity))

            # Spectral subtraction of side energy from mid channel
            side_ratio = mag_s / (mag_m + 1e-8)
            sub_mask = np.clip(1.0 - cfg.stereo_cancellation_strength * side_ratio, 0.0, 1.0)
            combined_mask = center_mask * sub_mask

            # Frequency Formant Bandpass Mask (Vocals primarily between 100Hz and 8500Hz)
            freq_mask = np.ones_like(f_bins)
            low_idx = np.searchsorted(f_bins, cfg.vocal_low_cutoff_hz)
            high_idx = np.searchsorted(f_bins, cfg.vocal_high_cutoff_hz)

            if low_idx > 0:
                freq_mask[:low_idx] = np.linspace(0.05, 1.0, low_idx) ** 2
            if high_idx < len(f_bins):
                freq_mask[high_idx:] = np.linspace(1.0, 0.05, len(f_bins) - high_idx) ** 2

            vocal_mask = combined_mask * freq_mask[:, np.newaxis]

            # Reconstruct Vocal Spectrum
            vocal_zxx = zxx_m * vocal_mask

            if progress_callback:
                progress_callback(60.0, "Synthesizing isolated vocal and accompaniment waveforms...")

            # Inverse STFT
            _, vocal_mono = signal.istft(vocal_zxx, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
            # Ensure matching sample length
            vocal_mono = vocal_mono[:total_samples]
            if len(vocal_mono) < total_samples:
                vocal_mono = np.pad(vocal_mono, (0, total_samples - len(vocal_mono)))

            # Vocal Track (stereo)
            vocals = np.stack([vocal_mono, vocal_mono], axis=0)

        else:
            # Mono Track: Spectral harmonic bandpass & formant filtering
            mono = audio[0] if audio.ndim > 1 else audio
            if progress_callback:
                progress_callback(35.0, "Applying speech formant tracking and harmonic isolation...")

            n_fft = 2048
            hop_length = 512
            win = np.hanning(n_fft)
            f_bins, t_frames, zxx = signal.stft(mono, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
            mag = np.abs(zxx)

            # Vocal Formant weighting
            freq_mask = np.ones_like(f_bins)
            low_idx = np.searchsorted(f_bins, cfg.vocal_low_cutoff_hz)
            high_idx = np.searchsorted(f_bins, cfg.vocal_high_cutoff_hz)
            if low_idx > 0:
                freq_mask[:low_idx] = 0.05
            if high_idx < len(f_bins):
                freq_mask[high_idx:] = 0.05

            # Dynamic Vocal Formant Emphasis (Speech energy peak ~ 300Hz - 3500Hz)
            vocal_zxx = zxx * freq_mask[:, np.newaxis]
            _, vocal_mono = signal.istft(vocal_zxx, fs=sample_rate, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
            vocal_mono = vocal_mono[:total_samples]
            if len(vocal_mono) < total_samples:
                vocal_mono = np.pad(vocal_mono, (0, total_samples - len(vocal_mono)))

            vocals = vocal_mono.copy()

        # Step 2: Post-Processing Filters (High-Pass, Voice Presence Boost, Limiter)
        if cfg.remove_drums_bass:
            vocals = FilterPipeline.high_pass(vocals, sample_rate, cutoff_hz=cfg.vocal_low_cutoff_hz)
            vocals = FilterPipeline.low_pass(vocals, sample_rate, cutoff_hz=cfg.vocal_high_cutoff_hz)

        if cfg.enhance_speech_formants:
            vocals = FilterPipeline.voice_presence_boost(vocals, sample_rate, gain_db=3.5)

        # Soft Noise Gating on Vocal Track to clear residual instrumental bleed in quiet pauses
        vocals = FilterPipeline.noise_gate(vocals, threshold_db=-46.0, sample_rate=sample_rate)

        # Step 3: Compute Instrumental / Accompaniment Track (Original minus Vocals)
        if progress_callback:
            progress_callback(80.0, "Computing clean instrumental accompaniment track...")

        instrumental = audio - vocals
        instrumental = FilterPipeline.soft_limiter(instrumental, threshold_dbfs=-0.5)

        if cfg.normalize_output:
            vocals = FilterPipeline.peak_normalize(vocals, target_dbfs=-1.0)
            instrumental = FilterPipeline.peak_normalize(instrumental, target_dbfs=-1.0)

        if progress_callback:
            progress_callback(100.0, "Vocal and instrumental separation completed.")

        return vocals.astype(np.float32), instrumental.astype(np.float32)

    @classmethod
    def extract_vocal_file(
        cls,
        input_media_path: Path | str,
        output_vocal_path: Optional[Path | str] = None,
        output_instrumental_path: Optional[Path | str] = None,
        config: Optional[VocalExtractionConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Extracts vocals and/or instrumental tracks from an audio or video file and saves them.

        Args:
            input_media_path: Source audio or video file.
            output_vocal_path: Destination path for extracted vocals (None to skip).
            output_instrumental_path: Destination path for instrumental track (None to skip).
            config: Separation parameters.
            progress_callback: Progress callback (0-100%).

        Returns:
            Tuple of (vocal_file_path, instrumental_file_path).
        """
        from src.utils.ffmpeg_helper import FFmpegHelper
        from src.core.video_engine import VideoEngine
        from src.utils.temp_manager import TempManager

        in_path = Path(input_media_path)
        if not in_path.exists():
            raise FileNotFoundError(f"Input file not found: {in_path}")

        if progress_callback:
            progress_callback(10.0, f"Loading audio stream from {in_path.name}...")

        is_vid = FFmpegHelper.is_video_file(in_path)
        if is_vid:
            temp_wav = VideoEngine.extract_audio(in_path, sample_rate=48000)
            try:
                audio_arr, sr = AudioIO.load_audio(temp_wav)
            finally:
                TempManager.remove_file(temp_wav)
        else:
            audio_arr, sr = AudioIO.load_audio(in_path)

        def _sub_prog(pct: float, msg: str):
            if progress_callback:
                scaled = 15.0 + (pct / 100.0) * 75.0
                progress_callback(scaled, msg)

        vocals, instrumental = cls.separate_audio(audio_arr, sr, config=config, progress_callback=_sub_prog)

        v_out: Optional[Path] = None
        i_out: Optional[Path] = None

        if output_vocal_path:
            v_out = Path(output_vocal_path)
            v_out.parent.mkdir(parents=True, exist_ok=True)
            if progress_callback:
                progress_callback(92.0, f"Saving isolated vocal track to {v_out.name}...")
            AudioIO.save_audio(vocals, sr, v_out)

        if output_instrumental_path:
            i_out = Path(output_instrumental_path)
            i_out.parent.mkdir(parents=True, exist_ok=True)
            if progress_callback:
                progress_callback(96.0, f"Saving instrumental track to {i_out.name}...")
            AudioIO.save_audio(instrumental, sr, i_out)

        if progress_callback:
            progress_callback(100.0, "Separation finished successfully.")

        return v_out, i_out

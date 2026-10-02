"""Video processing engine for extracting audio tracks, applying DSP denoise, and lossless stream-copy remuxing."""
from pathlib import Path
from typing import Optional, Callable
import soundfile as sf

from .audio_engine import AudioDenoiseEngine, DenoiseConfig
from src.utils.ffmpeg_helper import FFmpegHelper
from src.utils.temp_manager import TempManager
from src.utils.audio_io import AudioIO
from src.utils.logger import get_logger

logger = get_logger("VideoEngine")


class VideoEngine:
    """Orchestrates video audio extraction, DSP filtering, and zero-loss stream-copy remuxing."""

    @classmethod
    def extract_audio(
        cls,
        video_path: Path | str,
        output_wav_path: Optional[Path | str] = None,
        output_audio_path: Optional[Path | str] = None,
        sample_rate: int = 48000,
        audio_codec: Optional[str] = None,
        bitrate: str = "320k"
    ) -> Path:
        """Extracts the audio track from a video container into WAV, MP3, FLAC, AAC, or other formats.

        Args:
            video_path: Path to source video file.
            output_wav_path: Legacy argument for destination path.
            output_audio_path: Destination audio path. If None, creates a temporary WAV file.
            sample_rate: Audio sampling frequency in Hz (default 48kHz).
            audio_codec: Audio codec or 'copy' for direct stream extraction.
            bitrate: Audio bitrate for lossy formats (e.g., '320k').

        Returns:
            Path to the extracted audio file.
        """
        v_path = Path(video_path)
        if not v_path.exists():
            raise FileNotFoundError(f"Video file does not exist: {v_path}")

        target_path = output_audio_path or output_wav_path
        if target_path is None:
            out_path = TempManager.create_temp_file(suffix=".wav", prefix="extracted_")
        else:
            out_path = Path(target_path)

        FFmpegHelper.extract_audio(
            video_path=v_path,
            output_audio_path=out_path,
            sample_rate=sample_rate,
            channels=2,
            audio_codec=audio_codec,
            bitrate=bitrate
        )
        return out_path

    @classmethod
    def extract_sound(
        cls,
        video_path: Path | str,
        output_audio_path: Path | str,
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        sample_rate: int = 48000,
        bitrate: str = "320k",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Path:
        """High-level function to extract sound from a video with optional DSP noise reduction.

        Args:
            video_path: Source video file path.
            output_audio_path: Destination audio file path (.wav, .mp3, .flac, .aac, .m4a, .ogg).
            denoise: If True, applies noise suppression before saving. If False, extracts raw audio.
            config: Noise reduction configuration if denoise=True.
            sample_rate: Audio sampling frequency in Hz.
            bitrate: Bitrate for lossy formats (MP3/AAC).
            progress_callback: Optional callback for progress reporting (0-100%).

        Returns:
            Path to the saved audio file.
        """
        v_path = Path(video_path)
        out_path = Path(output_audio_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not denoise:
            # Fast direct extraction without DSP overhead
            if progress_callback:
                progress_callback(20.0, "Extracting audio track from video...")
            cls.extract_audio(
                video_path=v_path,
                output_audio_path=out_path,
                sample_rate=sample_rate,
                bitrate=bitrate
            )
            if progress_callback:
                progress_callback(100.0, f"Extracted raw audio: {out_path.name}")
            return out_path

        # Denoise mode: Extract -> Load -> Denoise -> Save
        temp_wav = TempManager.create_temp_file(suffix=".wav", prefix="extract_denoise_")
        try:
            if progress_callback:
                progress_callback(15.0, "Extracting audio stream for denoising...")
            cls.extract_audio(
                video_path=v_path,
                output_wav_path=temp_wav,
                sample_rate=sample_rate
            )

            if progress_callback:
                progress_callback(30.0, "Loading audio data...")
            audio_arr, sr = AudioIO.load_audio(temp_wav)

            def _audio_progress(pct: float, msg: str) -> None:
                if progress_callback:
                    scaled_pct = 30.0 + (pct / 100.0) * 55.0
                    progress_callback(scaled_pct, msg)

            cfg = config or DenoiseConfig()
            cleaned_arr = AudioDenoiseEngine.process_audio(
                audio=audio_arr,
                sample_rate=sr,
                config=cfg,
                progress_callback=_audio_progress
            )

            if progress_callback:
                progress_callback(90.0, f"Saving cleaned audio to {out_path.suffix.upper()}...")
            AudioIO.save_audio(cleaned_arr, sr, out_path)

            if progress_callback:
                progress_callback(100.0, f"Saved clean audio: {out_path.name}")
            return out_path
        finally:
            TempManager.remove_file(temp_wav)

    @classmethod
    def remux_audio(
        cls,
        original_video_path: Path | str,
        cleaned_audio_path: Path | str,
        output_video_path: Path | str,
        audio_codec: str = "aac",
        audio_bitrate: str = "320k"
    ) -> Path:
        """Remuxes clean audio into the original video container using stream-copy (-c:v copy).

        Args:
            original_video_path: Path to the original video file.
            cleaned_audio_path: Path to the denoised WAV file.
            output_video_path: Destination path for the output video.
            audio_codec: Target audio codec ('aac', 'flac', etc.).
            audio_bitrate: Bitrate for AAC encoding.

        Returns:
            Path to the saved remuxed video file.
        """
        out_path = Path(output_video_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        FFmpegHelper.remux_video_lossless(
            original_video_path=original_video_path,
            cleaned_audio_path=cleaned_audio_path,
            output_video_path=out_path,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate
        )
        return out_path

    @classmethod
    def process_video_file(
        cls,
        video_path: Path | str,
        output_video_path: Path | str,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Path:
        """Complete end-to-end pipeline: Video -> Audio Extract -> Denoise -> Lossless Remux -> Output.

        Args:
            video_path: Input video file.
            output_video_path: Output clean video file.
            config: Noise reduction configuration parameters.
            progress_callback: Optional progress reporter callback.

        Returns:
            Path to the completed output video file.
        """
        if config is None:
            config = DenoiseConfig()

        v_path = Path(video_path)
        temp_extracted_wav = TempManager.create_temp_file(suffix=".wav", prefix="vid_extract_")
        temp_cleaned_wav = TempManager.create_temp_file(suffix=".wav", prefix="vid_clean_")

        try:
            # Step 1: Audio Extraction
            if progress_callback:
                progress_callback(10.0, "Extracting audio from video...")
            cls.extract_audio(v_path, output_wav_path=temp_extracted_wav, sample_rate=48000)

            # Step 2: Load and Denoise Audio Array
            if progress_callback:
                progress_callback(25.0, "Loading audio stream...")
            audio_arr, sr = AudioIO.load_audio(temp_extracted_wav)

            def _audio_progress(pct: float, msg: str) -> None:
                if progress_callback:
                    # Map audio progress (25% to 85%)
                    scaled_pct = 25.0 + (pct / 100.0) * 60.0
                    progress_callback(scaled_pct, msg)

            cleaned_arr = AudioDenoiseEngine.process_audio(
                audio=audio_arr,
                sample_rate=sr,
                config=config,
                progress_callback=_audio_progress
            )

            # Step 3: Save clean audio to temp WAV
            if progress_callback:
                progress_callback(88.0, "Saving intermediate clean audio...")
            AudioIO.save_audio(cleaned_arr, sr, temp_cleaned_wav)

            # Step 4: Lossless Remux
            if progress_callback:
                progress_callback(92.0, "Remuxing clean audio with video (Stream Copy)...")
            final_out = cls.remux_audio(
                original_video_path=v_path,
                cleaned_audio_path=temp_cleaned_wav,
                output_video_path=output_video_path,
                audio_codec="aac",
                audio_bitrate="320k"
            )

            if progress_callback:
                progress_callback(100.0, "Video noise reduction finished.")

            logger.info(f"Successfully processed video: {final_out}")
            return final_out
        finally:
            TempManager.remove_file(temp_extracted_wav)
            TempManager.remove_file(temp_cleaned_wav)

    @classmethod
    def trim_video_range(
        cls,
        video_path: Path | str,
        start_sec: float,
        end_sec: float,
        output_path: Path | str,
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Path:
        """Trims a specific time range [start_sec, end_sec] from a video with optional audio denoising."""
        v_path = Path(video_path)
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.1, end_sec - start_sec)

        if not denoise:
            if progress_callback:
                progress_callback(30.0, f"Trimming video segment ({start_sec:.1f}s - {end_sec:.1f}s)...")
            FFmpegHelper.split_video_segment(
                video_path=v_path,
                output_path=out_path,
                start_sec=start_sec,
                duration_sec=duration,
                stream_copy=True
            )
            if progress_callback:
                progress_callback(100.0, f"Trimmed: {out_path.name}")
            return out_path

        # Trim first, then denoise
        temp_trimmed = TempManager.create_temp_file(suffix=v_path.suffix, prefix="temp_trim_")
        try:
            if progress_callback:
                progress_callback(20.0, "Extracting trimmed video slice...")
            FFmpegHelper.split_video_segment(
                video_path=v_path,
                output_path=temp_trimmed,
                start_sec=start_sec,
                duration_sec=duration,
                stream_copy=True
            )
            cls.process_video_file(
                video_path=temp_trimmed,
                output_video_path=out_path,
                config=config,
                progress_callback=progress_callback
            )
            return out_path
        finally:
            TempManager.remove_file(temp_trimmed)

    @classmethod
    def split_video_by_duration(
        cls,
        video_path: Path | str,
        segment_duration_sec: float,
        output_dir: Path | str,
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> list[Path]:
        """Splits video into equal duration chunks (e.g., 30s clips for YouTube Shorts, Reels, WhatsApp)."""
        v_path = Path(video_path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        total_duration = FFmpegHelper.get_media_duration(v_path)
        if total_duration <= 0.0:
            raise ValueError(f"Could not determine duration for video: {v_path.name}")

        segment_duration_sec = max(0.5, segment_duration_sec)
        num_segments = int(total_duration // segment_duration_sec)
        if total_duration % segment_duration_sec > 0.1:
            num_segments += 1

        output_files: list[Path] = []
        stem = v_path.stem
        ext = v_path.suffix

        for i in range(num_segments):
            start = i * segment_duration_sec
            dur = min(segment_duration_sec, total_duration - start)
            if dur <= 0.1:
                continue

            part_name = f"{stem}_part{i+1:03d}{ext}"
            part_path = out_dir / part_name

            if progress_callback:
                pct = (i / num_segments) * 100.0
                progress_callback(pct, f"Processing split segment {i+1}/{num_segments}...")

            cls.trim_video_range(
                video_path=v_path,
                start_sec=start,
                end_sec=start + dur,
                output_path=part_path,
                denoise=denoise,
                config=config
            )
            output_files.append(part_path)

        if progress_callback:
            progress_callback(100.0, f"Successfully created {len(output_files)} split video clips.")
        return output_files

    @classmethod
    def split_video_by_parts(
        cls,
        video_path: Path | str,
        num_parts: int,
        output_dir: Path | str,
        denoise: bool = False,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> list[Path]:
        """Splits video into N equal parts."""
        v_path = Path(video_path)
        total_duration = FFmpegHelper.get_media_duration(v_path)
        if total_duration <= 0.0:
            raise ValueError(f"Could not determine duration for video: {v_path.name}")

        num_parts = max(2, min(50, num_parts))
        seg_duration = total_duration / float(num_parts)
        return cls.split_video_by_duration(
            video_path=v_path,
            segment_duration_sec=seg_duration,
            output_dir=output_dir,
            denoise=denoise,
            config=config,
            progress_callback=progress_callback
        )

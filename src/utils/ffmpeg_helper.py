"""FFmpeg discovery, validation, probing, and execution helper."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Any
from .logger import get_logger

logger = get_logger("FFmpegHelper")


class FFmpegHelper:
    """Helper class for discovering and executing FFmpeg binary operations."""

    _ffmpeg_path: Optional[str] = None

    @classmethod
    def get_ffmpeg_path(cls) -> str:
        """Finds and caches a working path to the FFmpeg executable.

        Search order:
        1. Cached valid path
        2. System PATH (`ffmpeg` / `ffmpeg.exe`)
        3. Local project `bin/ffmpeg.exe` or `bin/ffmpeg`
        4. Bundled `imageio_ffmpeg` binary wheel
        """
        if cls._ffmpeg_path and Path(cls._ffmpeg_path).exists():
            return cls._ffmpeg_path

        # 1. System PATH
        sys_path = shutil.which("ffmpeg")
        if sys_path and cls._validate_binary(sys_path):
            cls._ffmpeg_path = sys_path
            logger.info(f"Found system FFmpeg: {sys_path}")
            return cls._ffmpeg_path

        # 2. Local bin/ directory
        project_root = Path(__file__).resolve().parent.parent.parent
        local_bin_names = ["ffmpeg.exe", "ffmpeg"]
        for name in local_bin_names:
            local_bin = project_root / "bin" / name
            if local_bin.exists() and cls._validate_binary(str(local_bin)):
                cls._ffmpeg_path = str(local_bin)
                logger.info(f"Found local FFmpeg binary: {cls._ffmpeg_path}")
                return cls._ffmpeg_path

        # 3. imageio-ffmpeg fallback
        try:
            import imageio_ffmpeg
            imgio_path = imageio_ffmpeg.get_ffmpeg_exe()
            if imgio_path and Path(imgio_path).exists() and cls._validate_binary(imgio_path):
                cls._ffmpeg_path = imgio_path
                logger.info(f"Using imageio-ffmpeg bundled binary: {cls._ffmpeg_path}")
                return cls._ffmpeg_path
        except ImportError:
            pass

        raise FileNotFoundError(
            "FFmpeg executable was not found on system PATH, local bin/, or imageio-ffmpeg package. "
            "Please install FFmpeg or install imageio-ffmpeg."
        )

    @staticmethod
    def _validate_binary(path: str) -> bool:
        """Executes ffmpeg -version to verify binary integrity."""
        try:
            res = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=5,
            )
            return res.returncode == 0
        except Exception as ex:
            logger.debug(f"Validation failed for FFmpeg at {path}: {ex}")
            return False

    @classmethod
    def has_audio_stream(cls, path: Path | str) -> bool:
        """Checks if a video or audio file contains at least one audio stream."""
        p = Path(path)
        if not p.exists():
            return False
        ffmpeg_bin = cls.get_ffmpeg_path()
        cmd = [ffmpeg_bin, "-i", str(p)]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=5
            )
            stderr_text = res.stderr.decode("utf-8", errors="ignore")
            return "Audio:" in stderr_text
        except Exception:
            return False

    @classmethod
    def is_video_file(cls, path: Path | str) -> bool:
        """Checks if a file has a common video container extension."""
        video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".ts"}
        return Path(path).suffix.lower() in video_extensions

    @classmethod
    def is_audio_file(cls, path: Path | str) -> bool:
        """Checks if a file has a common audio container extension."""
        audio_extensions = {".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".aiff", ".opus"}
        return Path(path).suffix.lower() in audio_extensions

    @classmethod
    def extract_audio(
        cls,
        video_path: Path | str,
        output_wav_path: Optional[Path | str] = None,
        output_audio_path: Optional[Path | str] = None,
        sample_rate: int = 48000,
        channels: int = 2,
        audio_codec: Optional[str] = None,
        bitrate: str = "320k"
    ) -> bool:
        """Extracts audio track from a video file into WAV, MP3, FLAC, AAC, or other audio formats.

        Args:
            video_path: Path to the input video file.
            output_wav_path: Legacy argument for destination path.
            output_audio_path: Destination path where extracted audio should be written.
            sample_rate: Target sample rate in Hz (default 48kHz).
            channels: Number of audio channels (1=mono, 2=stereo).
            audio_codec: Custom audio codec ('pcm_s16le', 'libmp3lame', 'flac', 'aac', 'copy', etc.).
            bitrate: Target audio bitrate for lossy formats (default '320k').

        Returns:
            True if extraction succeeded, False otherwise.
        """
        v_path = Path(video_path)
        if not v_path.exists():
            raise FileNotFoundError(f"Input file not found: {v_path}")

        # Check if the input file has an audio stream
        if not cls.has_audio_stream(v_path):
            raise ValueError(f"The video '{v_path.name}' contains no audio track (it is silent / has no audio stream).")

        dest_path = Path(output_audio_path or output_wav_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        ext = dest_path.suffix.lower()

        ffmpeg_bin = cls.get_ffmpeg_path()

        # Direct stream-copy if requested
        if audio_codec == "copy":
            cmd = [
                ffmpeg_bin, "-y",
                "-i", str(v_path),
                "-vn",
                "-c:a", "copy",
                str(dest_path)
            ]
        else:
            # Auto-detect codec from file extension if not explicitly specified
            if not audio_codec:
                if ext == ".mp3":
                    audio_codec = "libmp3lame"
                elif ext == ".flac":
                    audio_codec = "flac"
                elif ext in {".aac", ".m4a"}:
                    audio_codec = "aac"
                elif ext == ".ogg":
                    audio_codec = "libvorbis"
                else:
                    audio_codec = "pcm_s16le"

            cmd = [
                ffmpeg_bin, "-y",
                "-i", str(v_path),
                "-vn",
                "-c:a", audio_codec,
                "-ar", str(sample_rate),
                "-ac", str(channels),
            ]
            if audio_codec in {"libmp3lame", "aac"} and bitrate:
                cmd.extend(["-b:a", str(bitrate)])
            cmd.append(str(dest_path))

        logger.info(f"Extracting audio: {' '.join(cmd)}")
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                check=True
            )
            return dest_path.exists() and dest_path.stat().st_size > 0
        except subprocess.CalledProcessError as ex:
            err_text = ex.stderr.decode('utf-8', errors='ignore')
            logger.error(f"FFmpeg audio extraction failed: {err_text}")
            if "does not contain any stream" in err_text or "Output file does not contain" in err_text:
                raise ValueError(f"The video '{v_path.name}' contains no audio track to extract.")
            raise RuntimeError(f"FFmpeg extraction failed: {err_text.strip().splitlines()[-1] if err_text else str(ex)}")

    @classmethod
    def remux_video_lossless(
        cls,
        original_video_path: Path | str,
        cleaned_audio_path: Path | str,
        output_video_path: Path | str,
        audio_codec: str = "aac",
        audio_bitrate: str = "320k"
    ) -> bool:
        """Remuxes clean audio into video container using lossless video stream-copy (-c:v copy).

        Args:
            original_video_path: Input original video file.
            cleaned_audio_path: Denoised WAV file.
            output_video_path: Output target video file path.
            audio_codec: Target audio codec ('aac', 'flac', or 'copy').
            audio_bitrate: Target audio bitrate for lossy codecs.

        Returns:
            True if remuxing succeeded, False otherwise.
        """
        ffmpeg_bin = cls.get_ffmpeg_path()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(original_video_path),
            "-i", str(cleaned_audio_path),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:a", audio_codec,
        ]

        if audio_codec == "aac":
            cmd.extend(["-b:a", audio_bitrate])

        cmd.extend(["-shortest", str(output_video_path)])

        logger.info(f"Remuxing video with stream-copy: {' '.join(cmd)}")
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                check=True
            )
            return Path(output_video_path).exists() and Path(output_video_path).stat().st_size > 0
        except subprocess.CalledProcessError as ex:
            logger.error(f"FFmpeg video remux failed: {ex.stderr.decode('utf-8', errors='ignore')}")
            raise RuntimeError(f"FFmpeg video remux failed: {ex}")

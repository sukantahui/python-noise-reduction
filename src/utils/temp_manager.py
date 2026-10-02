"""Temporary workspace and resource lifecycle manager."""
import os
import shutil
import tempfile
import atexit
from pathlib import Path
from typing import Optional
from .logger import get_logger

logger = get_logger("TempManager")


class TempManager:
    """Manages temporary files and directories with automatic cleanup on exit."""

    _instance: Optional["TempManager"] = None
    _temp_dirs: list[Path] = []
    _temp_files: list[Path] = []

    def __new__(cls) -> "TempManager":
        if cls._instance is None:
            cls._instance = super(TempManager, cls).__new__(cls)
            atexit.register(cls.cleanup_all)
        return cls._instance

    @classmethod
    def create_temp_dir(cls, prefix: str = "noiserelief_") -> Path:
        """Creates a dedicated temporary directory tracked for cleanup."""
        d = Path(tempfile.mkdtemp(prefix=prefix))
        cls._temp_dirs.append(d)
        logger.debug(f"Created temporary workspace: {d}")
        return d

    @classmethod
    def create_temp_file(cls, suffix: str = ".wav", prefix: str = "temp_audio_") -> Path:
        """Creates a tracked temporary file path."""
        fd, path_str = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        path = Path(path_str)
        cls._temp_files.append(path)
        return path

    @classmethod
    def remove_file(cls, path: Path | str) -> None:
        """Safely removes a file if it exists."""
        p = Path(path)
        try:
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
                if p in cls._temp_files:
                    cls._temp_files.remove(p)
                logger.debug(f"Removed temp file: {p}")
        except Exception as ex:
            logger.warning(f"Failed to remove temp file {p}: {ex}")

    @classmethod
    def cleanup_all(cls) -> None:
        """Removes all registered temporary files and directories."""
        for file_path in cls._temp_files:
            try:
                if file_path.exists() and file_path.is_file():
                    file_path.unlink(missing_ok=True)
            except Exception as ex:
                logger.warning(f"Error cleaning file {file_path}: {ex}")
        cls._temp_files.clear()

        for dir_path in cls._temp_dirs:
            try:
                if dir_path.exists() and dir_path.is_dir():
                    shutil.rmtree(dir_path, ignore_errors=True)
            except Exception as ex:
                logger.warning(f"Error cleaning directory {dir_path}: {ex}")
        cls._temp_dirs.clear()
        logger.debug("Cleaned up all temporary resources.")

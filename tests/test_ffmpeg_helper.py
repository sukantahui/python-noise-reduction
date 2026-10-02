"""Tests for FFmpeg binary detection and file extension helpers."""
import pytest
from pathlib import Path
from src.utils.ffmpeg_helper import FFmpegHelper


def test_ffmpeg_path_discovery():
    """Verifies that FFmpeg binary is discovered via system or imageio-ffmpeg."""
    path = FFmpegHelper.get_ffmpeg_path()
    assert path is not None
    assert Path(path).exists()


def test_file_type_detection():
    """Verifies audio and video extension classification."""
    assert FFmpegHelper.is_video_file("test.mp4") is True
    assert FFmpegHelper.is_video_file("movie.mkv") is True
    assert FFmpegHelper.is_video_file("clip.mov") is True
    assert FFmpegHelper.is_video_file("song.wav") is False

    assert FFmpegHelper.is_audio_file("song.wav") is True
    assert FFmpegHelper.is_audio_file("track.mp3") is True
    assert FFmpegHelper.is_audio_file("audio.flac") is True
    assert FFmpegHelper.is_audio_file("video.mp4") is False

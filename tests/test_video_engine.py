"""Integration tests for the Video Engine (Audio extraction, Lossless Remuxing, and Video Splitting)."""
import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
from src.core.video_engine import VideoEngine
from src.core.audio_engine import DenoiseConfig
from src.utils.temp_manager import TempManager
from src.utils.ffmpeg_helper import FFmpegHelper
import subprocess
import os


@pytest.fixture
def synthetic_video_file(tmp_path) -> Path:
    """Generates a short 3-second synthetic MP4 test video with noisy audio using FFmpeg."""
    ffmpeg_bin = FFmpegHelper.get_ffmpeg_path()
    video_path = tmp_path / "synthetic_test.mp4"

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=30",
        "-f", "lavfi", "-i", "anoisesrc=d=3:c=pink:r=44100:a=0.1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(video_path)
    ]
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=True
    )
    return video_path


def test_video_audio_extraction(synthetic_video_file):
    """Verifies that audio can be extracted losslessly into a WAV container."""
    temp_wav = VideoEngine.extract_audio(synthetic_video_file)
    try:
        assert temp_wav.exists()
        assert temp_wav.stat().st_size > 0

        data, sr = sf.read(str(temp_wav))
        assert sr == 48000
        assert len(data) > 0
    finally:
        TempManager.remove_file(temp_wav)


def test_video_end_to_end_denoising(synthetic_video_file, tmp_path):
    """Verifies full Video -> Extract -> Denoise -> Lossless Remux pipeline."""
    output_video = tmp_path / "cleaned_output.mp4"
    config = DenoiseConfig(reduction_strength=0.80, stationary_mode=True)

    result_path = VideoEngine.process_video_file(
        video_path=synthetic_video_file,
        output_video_path=output_video,
        config=config
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_video_trim_range(synthetic_video_file, tmp_path):
    """Verifies trimming a specific time interval from a video."""
    trimmed_video = tmp_path / "trimmed_clip.mp4"
    res = VideoEngine.trim_video_range(
        video_path=synthetic_video_file,
        start_sec=0.5,
        end_sec=2.0,
        output_path=trimmed_video,
        denoise=False
    )
    assert res.exists()
    assert res.stat().st_size > 0


def test_video_split_by_duration(synthetic_video_file, tmp_path):
    """Verifies splitting video into 1-second segment clips."""
    split_dir = tmp_path / "split_clips"
    clips = VideoEngine.split_video_by_duration(
        video_path=synthetic_video_file,
        segment_duration_sec=1.0,
        output_dir=split_dir,
        denoise=False
    )
    assert len(clips) >= 2
    for c in clips:
        assert c.exists()
        assert c.stat().st_size > 0


def test_video_split_by_parts(synthetic_video_file, tmp_path):
    """Verifies splitting video into 2 equal parts."""
    parts_dir = tmp_path / "parts_output"
    parts = VideoEngine.split_video_by_parts(
        video_path=synthetic_video_file,
        num_parts=2,
        output_dir=parts_dir,
        denoise=False
    )
    assert len(parts) == 2
    for p in parts:
        assert p.exists()
        assert p.stat().st_size > 0


def test_video_extract_sound_raw_formats(synthetic_video_file, tmp_path):
    """Verifies raw audio extraction to MP3, FLAC, and WAV."""
    mp3_out = tmp_path / "extracted.mp3"
    flac_out = tmp_path / "extracted.flac"
    wav_out = tmp_path / "extracted.wav"

    # 1. MP3 extraction
    res_mp3 = VideoEngine.extract_sound(synthetic_video_file, mp3_out, denoise=False)
    assert res_mp3.exists()
    assert res_mp3.stat().st_size > 0

    # 2. FLAC extraction
    res_flac = VideoEngine.extract_sound(synthetic_video_file, flac_out, denoise=False)
    assert res_flac.exists()
    assert res_flac.stat().st_size > 0

    # 3. WAV extraction
    res_wav = VideoEngine.extract_sound(synthetic_video_file, wav_out, denoise=False)
    assert res_wav.exists()
    assert res_wav.stat().st_size > 0


def test_video_extract_sound_denoised(synthetic_video_file, tmp_path):
    """Verifies extracting cleaned/denoised audio directly from video."""
    denoised_wav = tmp_path / "denoised_sound.wav"
    config = DenoiseConfig(reduction_strength=0.75, stationary_mode=True)

    res = VideoEngine.extract_sound(
        video_path=synthetic_video_file,
        output_audio_path=denoised_wav,
        denoise=True,
        config=config
    )

    assert res.exists()
    assert res.stat().st_size > 0
    data, sr = sf.read(str(res))
    assert sr == 48000
    assert len(data) > 0

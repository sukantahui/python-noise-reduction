"""Integration tests for the Video Engine (Audio extraction and Lossless Remuxing)."""
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
    """Generates a short 2-second synthetic MP4 test video with noisy audio using FFmpeg."""
    ffmpeg_bin = FFmpegHelper.get_ffmpeg_path()
    video_path = tmp_path / "synthetic_test.mp4"

    # Generate synthetic video: 2-second color test pattern with 440Hz sine + noise audio
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
        "-f", "lavfi", "-i", "anoisesrc=d=2:c=pink:r=44100:a=0.1",
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


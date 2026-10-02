"""Tests for the core Audio Denoising Engine and SNR improvement calculations."""
import pytest
import numpy as np
from src.core.audio_engine import AudioDenoiseEngine, DenoiseConfig
from src.core.audio_analyzer import AudioAnalyzer


def test_audio_denoise_noise_reduction(synthetic_noisy_audio):
    """Verifies that spectral gating significantly attenuates noise power during pauses."""
    noisy = synthetic_noisy_audio["noisy"]
    sr = synthetic_noisy_audio["sr"]
    noise_mask = synthetic_noisy_audio["noise_only_mask"]

    config = DenoiseConfig(
        reduction_strength=0.90,
        stationary_mode=True,
        high_pass_hz=80.0,
        notch_50hz=True,
        noise_gate_db=-45.0,
        auto_noise_profile=True,
        normalize=False
    )

    denoised = AudioDenoiseEngine.process_audio(noisy, sample_rate=sr, config=config)

    assert denoised.shape == noisy.shape
    assert denoised.dtype == np.float32

    # Measure noise power reduction during background silence intervals
    initial_noise_power = np.mean(noisy[noise_mask] ** 2)
    cleaned_noise_power = np.mean(denoised[noise_mask] ** 2)

    noise_attenuation_db = 10.0 * np.log10(initial_noise_power / (cleaned_noise_power + 1e-12))
    assert noise_attenuation_db >= 10.0, f"Expected >= 10dB noise reduction, got {noise_attenuation_db:.2f}dB"


def test_extract_noise_profile(synthetic_noisy_audio):
    """Verifies that automatic noise profiling finds a valid background noise window."""
    noisy = synthetic_noisy_audio["noisy"]
    sr = synthetic_noisy_audio["sr"]
    profile = AudioDenoiseEngine.extract_noise_profile(noisy, sample_rate=sr, duration_sec=0.4)
    assert profile is not None
    assert len(profile) == int(sr * 0.4)


def test_audio_analyzer_downsampling(synthetic_clean_audio):
    """Verifies that waveform downsampling produces matching min and max envelope arrays."""
    min_env, max_env = AudioAnalyzer.downsample_waveform(synthetic_clean_audio, num_bins=500)
    assert len(min_env) == 500
    assert len(max_env) == 500
    assert np.all(max_env >= min_env)


def test_audio_analyzer_metrics(synthetic_noisy_audio):
    """Verifies that AudioAnalyzer calculates valid audio quality metrics."""
    noisy = synthetic_noisy_audio["noisy"]
    sr = synthetic_noisy_audio["sr"]
    denoised = AudioDenoiseEngine.process_audio(noisy, sample_rate=sr)

    metrics = AudioAnalyzer.get_audio_metrics(noisy, denoised, sample_rate=sr)
    assert "snr_gain_db" in metrics
    assert "noise_attenuation_db" in metrics
    assert "clean_noise_floor_dbfs" in metrics
    assert metrics["snr_gain_db"] >= 0.0


def test_audio_engine_presets():
    """Verifies that standard presets can be fetched and modified independently."""
    preset1 = AudioDenoiseEngine.get_preset("Default Studio Voice")
    assert preset1.reduction_strength == 0.80
    assert preset1.voice_clarity_boost is True

    preset2 = AudioDenoiseEngine.get_preset("Mild Background Hiss")
    assert preset2.reduction_strength == 0.55


def test_trim_audio_range(tmp_path, synthetic_clean_audio, sample_rate):
    """Verifies that trim_audio_range accurately slices an audio file."""
    from src.utils.audio_io import AudioIO
    wav_path = tmp_path / "test_input.wav"
    out_path = tmp_path / "test_trimmed.wav"
    AudioIO.save_audio(synthetic_clean_audio, sample_rate, wav_path)

    res = AudioDenoiseEngine.trim_audio_range(
        audio_path=wav_path,
        start_sec=0.5,
        end_sec=1.5,
        output_path=out_path,
        denoise=False
    )
    assert res.exists()
    loaded, sr = AudioIO.load_audio(res)
    assert sr == sample_rate
    # Duration should be ~1.0 second (44100 samples)
    assert abs(loaded.shape[-1] - 44100) < 50


def test_split_audio_by_duration(tmp_path, synthetic_clean_audio, sample_rate):
    """Verifies that split_audio_by_duration produces segments of expected lengths."""
    from src.utils.audio_io import AudioIO
    wav_path = tmp_path / "test_input_dur.wav"
    out_dir = tmp_path / "dur_segments"
    AudioIO.save_audio(synthetic_clean_audio, sample_rate, wav_path)  # 2.0s

    segments = AudioDenoiseEngine.split_audio_by_duration(
        audio_path=wav_path,
        segment_duration_sec=1.0,
        output_dir=out_dir,
        output_format="wav"
    )
    assert len(segments) == 2
    for seg in segments:
        assert seg.exists()


def test_split_audio_by_parts(tmp_path, synthetic_clean_audio, sample_rate):
    """Verifies that split_audio_by_parts splits an audio track into N equal pieces."""
    from src.utils.audio_io import AudioIO
    wav_path = tmp_path / "test_input_parts.wav"
    out_dir = tmp_path / "parts_segments"
    AudioIO.save_audio(synthetic_clean_audio, sample_rate, wav_path)  # 2.0s

    segments = AudioDenoiseEngine.split_audio_by_parts(
        audio_path=wav_path,
        num_parts=4,
        output_dir=out_dir,
        output_format="wav"
    )
    assert len(segments) == 4
    for seg in segments:
        assert seg.exists()


def test_split_audio_by_silence(tmp_path, sample_rate):
    """Verifies silence detection and splitting on audio containing speech takes with pauses."""
    from src.utils.audio_io import AudioIO
    # Create 5s audio with tone, 1s silence, tone
    t = np.linspace(0, 5.0, int(sample_rate * 5.0), endpoint=False)
    signal = np.zeros_like(t)
    # Take 1: 0.0s to 1.8s
    take1_idx = (t >= 0.0) & (t <= 1.8)
    signal[take1_idx] = 0.5 * np.sin(2 * np.pi * 440 * t[take1_idx])
    # Silence: 1.8s to 3.0s (1.2s pause)
    # Take 2: 3.0s to 5.0s
    take2_idx = (t >= 3.0) & (t <= 5.0)
    signal[take2_idx] = 0.5 * np.sin(2 * np.pi * 880 * t[take2_idx])

    wav_path = tmp_path / "speech_with_pauses.wav"
    out_dir = tmp_path / "silence_takes"
    AudioIO.save_audio(signal.astype(np.float32), sample_rate, wav_path)

    takes = AudioDenoiseEngine.split_audio_by_silence(
        audio_path=wav_path,
        output_dir=out_dir,
        min_silence_len_sec=0.8,
        silence_threshold_db=-30.0,
        output_format="wav"
    )
    assert len(takes) >= 2
    for take in takes:
        assert take.exists()


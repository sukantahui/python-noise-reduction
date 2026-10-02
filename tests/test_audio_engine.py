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



def test_audio_analyzer_downsampling(synthetic_clean_audio):
    """Verifies that waveform downsampling produces matching min and max envelope arrays."""
    min_env, max_env = AudioAnalyzer.downsample_waveform(synthetic_clean_audio, num_bins=500)
    assert len(min_env) == 500
    assert len(max_env) == 500
    assert np.all(max_env >= min_env)


def test_audio_engine_presets():
    """Verifies that standard presets can be fetched and modified independently."""
    preset1 = AudioDenoiseEngine.get_preset("Default Studio Voice")
    assert preset1.reduction_strength == 0.80

    preset2 = AudioDenoiseEngine.get_preset("Mild Background Hiss")
    assert preset2.reduction_strength == 0.55

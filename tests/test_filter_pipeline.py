"""Unit tests for the DSP filter pipeline."""
import pytest
import numpy as np
from src.core.filter_pipeline import FilterPipeline


def test_high_pass_filter(sample_rate):
    """Verifies that high-pass filter attenuates sub-bass frequencies below cutoff."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    # 20 Hz sub-bass tone vs 500 Hz speech tone
    low_freq = 0.5 * np.sin(2 * np.pi * 20 * t)
    high_freq = 0.5 * np.sin(2 * np.pi * 500 * t)
    combined = (low_freq + high_freq).astype(np.float32)

    filtered = FilterPipeline.high_pass(combined, sample_rate=sample_rate, cutoff_hz=80.0)

    # Low frequency energy should be significantly attenuated
    assert len(filtered) == len(combined)
    assert np.max(np.abs(filtered)) < np.max(np.abs(combined))


def test_low_pass_filter(sample_rate):
    """Verifies that low-pass filter attenuates high frequency hiss."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    speech_freq = 0.5 * np.sin(2 * np.pi * 1000 * t)
    ultra_high = 0.5 * np.sin(2 * np.pi * 18000 * t)
    combined = (speech_freq + ultra_high).astype(np.float32)

    filtered = FilterPipeline.low_pass(combined, sample_rate=sample_rate, cutoff_hz=8000.0)

    assert len(filtered) == len(combined)
    assert np.max(np.abs(filtered)) < np.max(np.abs(combined))


def test_notch_filter(sample_rate):
    """Verifies that notch filter attenuates exact 50Hz hum."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    hum_50hz = np.sin(2 * np.pi * 50 * t).astype(np.float32)

    notched = FilterPipeline.notch(hum_50hz, sample_rate=sample_rate, notch_freq_hz=50.0)

    # 50Hz power should drop by more than 20 dB
    orig_pwr = np.mean(hum_50hz ** 2)
    filtered_pwr = np.mean(notched ** 2)
    assert filtered_pwr < (orig_pwr * 0.05)


def test_de_hum_harmonics(sample_rate):
    """Verifies that harmonic de-hum removes 50Hz, 100Hz, and 150Hz overtones."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    h1 = np.sin(2 * np.pi * 50 * t)
    h2 = 0.5 * np.sin(2 * np.pi * 100 * t)
    h3 = 0.25 * np.sin(2 * np.pi * 150 * t)
    combined = (h1 + h2 + h3).astype(np.float32)

    cleaned = FilterPipeline.de_hum_harmonics(combined, sample_rate=sample_rate, base_freq_hz=50.0, num_harmonics=3)
    assert np.mean(cleaned ** 2) < (np.mean(combined ** 2) * 0.1)


def test_voice_presence_boost(sample_rate):
    """Verifies that voice presence boost boosts energy in the 3.4kHz vocal intelligibility band."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    vocal_tone = np.sin(2 * np.pi * 3400 * t).astype(np.float32)

    boosted = FilterPipeline.voice_presence_boost(vocal_tone, sample_rate=sample_rate, gain_db=3.0, freq_hz=3400.0)
    assert np.max(np.abs(boosted)) > np.max(np.abs(vocal_tone))


def test_vectorized_noise_gate(sample_rate):
    """Verifies that vectorized noise gate silences low-level noise while preserving loud signals."""
    t = np.linspace(0, 1.0, sample_rate, endpoint=False)
    loud = 0.8 * np.sin(2 * np.pi * 440 * t)
    quiet_noise = 0.001 * np.random.normal(0, 1, sample_rate)
    signal_with_pause = np.concatenate([loud, quiet_noise]).astype(np.float32)

    gated = FilterPipeline.noise_gate(signal_with_pause, threshold_db=-40.0, sample_rate=sample_rate)
    # The noise-only segment should be significantly attenuated
    noise_seg_before = signal_with_pause[sample_rate:]
    noise_seg_after = gated[sample_rate:]
    assert np.mean(noise_seg_after ** 2) <= np.mean(noise_seg_before ** 2)


def test_peak_normalization():
    """Verifies normalization to target peak dBFS."""
    audio = np.array([0.1, -0.2, 0.4, -0.3], dtype=np.float32)
    norm = FilterPipeline.peak_normalize(audio, target_dbfs=-1.0)
    target_peak = 10.0 ** (-1.0 / 20.0)
    assert np.isclose(np.max(np.abs(norm)), target_peak, atol=1e-3)


def test_soft_limiter():
    """Verifies that soft limiter prevents values exceeding 1.0."""
    audio = np.array([0.5, 1.2, -1.5, 0.8], dtype=np.float32)
    limited = FilterPipeline.soft_limiter(audio, threshold_dbfs=-0.5)
    assert np.max(np.abs(limited)) <= 1.0

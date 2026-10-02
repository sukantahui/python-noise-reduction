"""Pytest configuration and synthetic audio signal fixtures."""
import pytest
import numpy as np
from pathlib import Path
import sys

# Ensure src is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_rate() -> int:
    return 44100


@pytest.fixture
def synthetic_clean_audio(sample_rate) -> np.ndarray:
    """Generates 2 seconds of clean multi-harmonic 440 Hz tone."""
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Fundamental 440Hz + 2nd harmonic 880Hz
    signal = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.25 * np.sin(2 * np.pi * 880 * t)
    return signal.astype(np.float32)


@pytest.fixture
def synthetic_noisy_audio(sample_rate) -> dict:
    """Generates an audio track with initial silence/noise followed by a speech/harmonic tone."""
    duration = 3.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # 0.5s noise, 2.0s tone, 0.5s noise
    clean_signal = np.zeros_like(t)
    tone_idx = (t >= 0.5) & (t <= 2.5)
    clean_signal[tone_idx] = 0.5 * np.sin(2 * np.pi * 440 * t[tone_idx]) + 0.25 * np.sin(2 * np.pi * 880 * t[tone_idx])
    
    # Add stationary 50Hz hum and white noise across whole duration
    hum = 0.10 * np.sin(2 * np.pi * 50 * t)
    np.random.seed(42)
    white_noise = 0.05 * np.random.normal(0, 1, len(t))
    
    noisy_signal = clean_signal + hum + white_noise
    return {
        "clean": clean_signal.astype(np.float32),
        "noisy": noisy_signal.astype(np.float32),
        "sr": sample_rate,
        "duration": duration,
        "noise_only_mask": (t < 0.5) | (t > 2.5)
    }


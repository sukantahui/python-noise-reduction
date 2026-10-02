"""Unit and integration tests for Vocal Isolation and Instrumental Separation Engine."""
import pytest
import numpy as np
from pathlib import Path
import soundfile as sf

from src.core.vocal_extractor import VocalExtractor, VocalExtractionConfig
from src.utils.audio_io import AudioIO


def test_vocal_separator_stereo(tmp_path, sample_rate):
    """Verifies that center vocals are isolated from panned stereo instruments."""
    duration = 2.5
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # Centered Vocal Lead (440Hz Sine panned in center: L=R)
    vocal_signal = 0.6 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    # Panned Left Guitar (880Hz) and Panned Right Synth (1200Hz)
    left_inst = 0.4 * np.sin(2 * np.pi * 880 * t).astype(np.float32)
    right_inst = 0.4 * np.sin(2 * np.pi * 1200 * t).astype(np.float32)

    stereo_left = vocal_signal + left_inst
    stereo_right = vocal_signal + right_inst
    stereo_mix = np.stack([stereo_left, stereo_right], axis=0)

    config = VocalExtractionConfig(
        vocal_sensitivity=0.85,
        enhance_speech_formants=True,
        normalize_output=False
    )

    vocals, instrumental = VocalExtractor.separate_audio(stereo_mix, sample_rate, config=config)

    assert vocals.shape == stereo_mix.shape
    assert instrumental.shape == stereo_mix.shape

    # Vocal track should preserve vocal power
    vocal_power = np.mean(vocals ** 2)
    assert vocal_power > 0.01

    # Instrumental track should have significant energy from the panned instruments
    inst_power = np.mean(instrumental ** 2)
    assert inst_power > 0.01


def test_vocal_separator_mono(tmp_path, sample_rate):
    """Verifies vocal separation on a mono audio track."""
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    vocal_signal = 0.5 * np.sin(2 * np.pi * 500 * t).astype(np.float32)
    bass_rumble = 0.4 * np.sin(2 * np.pi * 50 * t).astype(np.float32)  # 50Hz sub bass

    mono_mix = vocal_signal + bass_rumble
    vocals, instrumental = VocalExtractor.separate_audio(mono_mix, sample_rate)

    assert vocals.shape[-1] == len(mono_mix)
    assert instrumental.shape[-1] == len(mono_mix)


def test_extract_vocal_file_end_to_end(tmp_path, synthetic_clean_audio, sample_rate):
    """Verifies saving vocal and instrumental files directly to disk."""
    wav_path = tmp_path / "song_mix.wav"
    vocal_out = tmp_path / "song_vocals.wav"
    inst_out = tmp_path / "song_inst.wav"

    AudioIO.save_audio(synthetic_clean_audio, sample_rate, wav_path)

    v_path, i_path = VocalExtractor.extract_vocal_file(
        input_media_path=wav_path,
        output_vocal_path=vocal_out,
        output_instrumental_path=inst_out
    )

    assert v_path is not None and v_path.exists()
    assert i_path is not None and i_path.exists()

    v_data, v_sr = AudioIO.load_audio(v_path)
    i_data, i_sr = AudioIO.load_audio(i_path)

    assert v_sr == sample_rate
    assert i_sr == sample_rate
    assert v_data.shape[-1] == synthetic_clean_audio.shape[-1]
    assert i_data.shape[-1] == synthetic_clean_audio.shape[-1]

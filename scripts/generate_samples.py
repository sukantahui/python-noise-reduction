"""Generates realistic audio and video sample files with diverse noise profiles for software testing."""
import numpy as np
import soundfile as sf
import subprocess
from pathlib import Path
import sys
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.ffmpeg_helper import FFmpegHelper
from src.utils.audio_io import AudioIO


def generate_speech_envelope(t: np.ndarray) -> np.ndarray:
    """Simulates speech phrases and pauses using smoothed envelopes."""
    # Create speech phrase intervals
    phrase1 = np.exp(-((t - 1.5) ** 2) / (2 * 0.4 ** 2))
    phrase2 = np.exp(-((t - 3.5) ** 2) / (2 * 0.6 ** 2))
    phrase3 = np.exp(-((t - 6.0) ** 2) / (2 * 0.8 ** 2))
    phrase4 = np.exp(-((t - 8.5) ** 2) / (2 * 0.5 ** 2))
    return np.clip(phrase1 + phrase2 + phrase3 + phrase4, 0.0, 1.0)


def generate_voice_formants(t: np.ndarray, f0: float = 140.0) -> np.ndarray:
    """Simulates voice harmonics (fundamental + formants)."""
    h1 = 0.50 * np.sin(2 * np.pi * f0 * t)
    h2 = 0.35 * np.sin(2 * np.pi * (2 * f0) * t)
    h3 = 0.20 * np.sin(2 * np.pi * (3 * f0) * t)
    h4 = 0.15 * np.sin(2 * np.pi * 1200 * t)  # Formant F1
    h5 = 0.10 * np.sin(2 * np.pi * 2400 * t)  # Formant F2
    return (h1 + h2 + h3 + h4 + h5).astype(np.float32)


def main():
    samples_dir = PROJECT_ROOT / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    sr = 44100
    duration = 10.0  # 10 seconds
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    np.random.seed(101)

    print("Generating sample test files in:", samples_dir)

    # -------------------------------------------------------------
    # 1. Sample 1: Podcast Voice with AC Hum & White Hiss (WAV)
    # -------------------------------------------------------------
    speech_env = generate_speech_envelope(t)
    voice_sig = generate_voice_formants(t, f0=130.0) * speech_env

    # Noise: 50Hz electrical hum + harmonics + HVAC rumble + white hiss
    hum = 0.12 * np.sin(2 * np.pi * 50 * t) + 0.04 * np.sin(2 * np.pi * 100 * t)
    hvac_rumble = 0.08 * np.sin(2 * np.pi * 35 * t)
    white_hiss = 0.04 * np.random.normal(0, 1, len(t))
    noisy_podcast = voice_sig + hum + hvac_rumble + white_hiss

    # Stereo modulation (subtle pan)
    stereo_podcast = np.vstack([noisy_podcast * 0.9, noisy_podcast * 0.95]).astype(np.float32)
    sample1_path = samples_dir / "podcast_interview_noisy.wav"
    AudioIO.save_audio(stereo_podcast, sr, sample1_path)
    print(f"  [+] Created: {sample1_path.name}")

    # -------------------------------------------------------------
    # 2. Sample 2: Outdoor Voice with Traffic & Wind Rumble (MP3)
    # -------------------------------------------------------------
    voice_sig2 = generate_voice_formants(t, f0=210.0) * speech_env  # Higher pitch voice
    # Non-stationary wind gusts & low frequency urban drone
    wind_mod = 0.5 * (1.0 + np.sin(2 * np.pi * 0.3 * t))
    wind_noise = 0.12 * wind_mod * np.random.normal(0, 1, len(t))
    traffic_rumble = 0.10 * np.sin(2 * np.pi * 42 * t) + 0.06 * np.sin(2 * np.pi * 78 * t)
    noisy_outdoor = (voice_sig2 + wind_noise + traffic_rumble).astype(np.float32)

    sample2_path = samples_dir / "outdoor_voice_wind_traffic.wav"
    AudioIO.save_audio(noisy_outdoor, sr, sample2_path)
    print(f"  [+] Created: {sample2_path.name}")

    # -------------------------------------------------------------
    # 3. Sample 3: Heavy Air Conditioner & Fan Noise (WAV)
    # -------------------------------------------------------------
    fan_fundamental = 0.20 * np.sin(2 * np.pi * 120 * t)
    fan_harmonics = 0.10 * np.sin(2 * np.pi * 240 * t) + 0.05 * np.sin(2 * np.pi * 360 * t)
    air_flow = 0.07 * np.random.normal(0, 1, len(t))
    noisy_ac = (voice_sig * 0.7 + fan_fundamental + fan_harmonics + air_flow).astype(np.float32)

    sample3_path = samples_dir / "ac_fan_noise_heavy.wav"
    AudioIO.save_audio(noisy_ac, sr, sample3_path)
    print(f"  [+] Created: {sample3_path.name}")

    # -------------------------------------------------------------
    # 4. Sample 4: Video Clip with Noisy Audio Track (MP4)
    # -------------------------------------------------------------
    ffmpeg_bin = FFmpegHelper.get_ffmpeg_path()
    sample4_video_path = samples_dir / "video_podcast_interview_noisy.mp4"

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration=10:size=640x360:rate=30",
        "-i", str(sample1_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(sample4_video_path)
    ]
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=True
    )
    print(f"  [+] Created: {sample4_video_path.name} (10-second test video)")


    print("\nAll test sample files created successfully in:", samples_dir)


if __name__ == "__main__":
    main()

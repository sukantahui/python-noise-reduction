# Project Documentation & Contribution Blueprint

> **Project Name**: NoiseRelief Studio — Audio & Video Noise Reduction Software  
> **Created By**: Coder & AccoTax ([www.codernaccotax.co.in](https://www.codernaccotax.co.in) | Ph: 7003756860)  
> **Repository**: `sukantahui/python-audio-noise-reduction`  
> **Current Version**: `1.0.0`


---

## 1. Executive Summary

NoiseRelief Studio is an open-source, high-performance desktop application engineered in Python to make professional-grade audio and video noise reduction accessible, instantaneous, and visually intuitive. 

By combining **vectorized Spectral Gating DSP algorithms** with **FFmpeg lossless video stream muxing**, the software allows podcasters, content creators, educators, and engineers to clean noisy audio tracks from audio and video recordings without requiring complex DAWs or slow video re-rendering pipelines.

---

## 2. Module Responsibilities & Ownership Matrix

```mermaid
flowchart TD
    subgraph Package_src ["src/ Source Package Breakdown"]
        M_CORE["src/core/\n- audio_engine.py\n- video_engine.py\n- filter_pipeline.py\n- audio_analyzer.py"]
        M_GUI["src/gui/\n- app.py\n- theme.py\n- components/*.py"]
        M_UTILS["src/utils/\n- ffmpeg_helper.py\n- audio_io.py\n- logger.py\n- temp_manager.py"]
    end

    M_CORE -->|"Provides Headless DSP & Remux Services"| M_GUI
    M_UTILS -->|"Provides I/O & System Helpers"| M_CORE
    M_UTILS -->|"Provides Theming & Loggers"| M_GUI
```

| Module Path | Primary Responsibility | Key Interfaces & Classes |
| :--- | :--- | :--- |
| `src/core/audio_engine.py` | Noise reduction algorithms, STFT computation, spectral gating masks | `NoiseReductionEngine`, `reduce_noise()` |
| `src/core/video_engine.py` | FFmpeg audio demuxing and lossless video remuxing | `VideoEngine`, `extract_audio()`, `remux_video()` |
| `src/core/filter_pipeline.py` | High-pass, low-pass, notch, noise gate, and normalizers | `FilterPipeline`, `apply_highpass()`, `apply_gate()` |
| `src/core/audio_analyzer.py` | Waveform min-max downsampling and SNR computation | `AudioAnalyzer`, `compute_waveform_envelope()`, `estimate_snr()` |
| `src/gui/app.py` | Main CustomTkinter application window and thread dispatcher | `NoiseReductionApp` |
| `src/gui/components/` | Modular UI widgets (DropZone, Waveform, Controls, Settings) | `DropZone`, `WaveformWidget`, `PlayerControls`, `SettingsPanel` |
| `src/utils/ffmpeg_helper.py` | FFmpeg detection, path resolution, and command execution | `FFmpegHelper`, `get_ffmpeg_path()`, `run_ffmpeg()` |
| `src/utils/audio_io.py` | Soundfile / Librosa audio reading and multi-format saving | `AudioIO`, `load_audio()`, `save_audio()` |

---

## 3. Development & Release Roadmap

```mermaid
gantt
    title NoiseRelief Studio Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Architecture & Setup
    Doc Architecture & Agent Specs    :done, 2026-10-01, 1d
    Project Skeleton & Dependencies   :active, 2026-10-02, 1d
    section Phase 2: Core Processing Engine
    Audio DSP & Filter Pipeline       :2026-10-03, 2d
    FFmpeg Video Demux/Remux Engine   :2026-10-05, 1d
    Signal Analyzer & SNR Metrics     :2026-10-06, 1d
    section Phase 3: GUI & Visualization
    CustomTkinter Layout & Dark Theme :2026-10-07, 2d
    Waveform & Live A/B Player        :2026-10-09, 2d
    Settings Panel & Presets          :2026-10-11, 1d
    section Phase 4: Batch & Verification
    Batch Processing Queue            :2026-10-12, 1d
    Test Suite & Synthetic Benchmarks :2026-10-13, 2d
    Standalone Packaging (.exe / .app):2026-10-15, 1d
```

---

## 4. Coding & Contribution Guidelines

1. **Format & Linting**: Use `black` (line length 100) and `ruff` / `flake8`.
2. **Type Safety**: All PRs must pass `mypy` static type analysis without errors.
3. **Unit Tests**: Every new DSP filter or video function must include corresponding unit tests in `tests/`.
4. **Git Commit Conventions**: Use Conventional Commits format (`feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`).

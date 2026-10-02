# AGENTS.md — AI Agent Operating Guidelines

> **Target Audience**: Any AI Agent, LLM, or software engineer working on this repository.  
> **Repository Purpose**: Python Desktop GUI Software for Audio & Video Background Noise Reduction.

---

## 1. Core Mission & Philosophy

This repository implements a **Modern Python Desktop GUI Application** capable of removing background noise (hiss, hum, air conditioning, fan noise, urban rumble, stationary and non-stationary noise) from both **standalone audio files** and **video tracks**.

### Core Guarantees:
1. **Audio Noise Suppression**: High-fidelity spectral gating and adaptive DSP noise reduction with adjustable reduction strength, stationary/non-stationary modes, frequency roll-off, and output gain/normalization.
2. **Video Audio Extraction & Lossless Remuxing**: If a video file is supplied (`.mp4`, `.mkv`, `.mov`, `.avi`), extract audio losslessly to temporary storage, perform noise reduction, and remux the cleaned audio track directly back into the original video container using **FFmpeg stream-copy (`-c:v copy`)** — zero quality loss and near-instant processing.
3. **Interactive Side-by-Side A/B Preview**: Real-time waveform & spectrogram comparison of "Original" vs. "Denoised" with interactive playback, seeking, and instant A/B switching before exporting.
4. **100% Non-Blocking Desktop GUI**: Modern Dark-Themed GUI built in Python (CustomTkinter / PySide6) with all signal processing and FFmpeg tasks executed on decoupled background threads.

---

## 2. Authoritative Documentation Index (`doc/`)

Before writing or modifying any code, all agents MUST consult the authoritative documents located in the `doc/` directory:

| Document | Purpose & Key Contents |
| :--- | :--- |
| [`doc/system_architecture.md`](file:///e:/python%20audio%20noise%20reduction/doc/system_architecture.md) | High-level system architecture, audio DSP pipeline, FFmpeg remuxing engine, threading model, and Mermaid flowcharts |
| [`doc/feature_specifications.md`](file:///e:/python%20audio%20noise%20reduction/doc/feature_specifications.md) | Detailed feature epics, audio/video format matrix, noise reduction parameters, batch processing, and acceptance criteria |
| [`doc/tech_stack_and_engine.md`](file:///e:/python%20audio%20noise%20reduction/doc/tech_stack_and_engine.md) | Technical stack rationale (`soundfile`, `scipy`, `noisereduce`, `ffmpeg`, `customtkinter`, `pygame`), performance benchmarks |
| [`doc/ui_ux_design.md`](file:///e:/python%20audio%20noise%20reduction/doc/ui_ux_design.md) | UI layout wireframes, dark-mode design tokens, waveform & A/B preview widgets, drag-and-drop dropzones |
| [`doc/testing_and_verification.md`](file:///e:/python%20audio%20noise%20reduction/doc/testing_and_verification.md) | Unit test suite, synthetic noise generator fixtures, SNR (Signal-to-Noise Ratio) verification, video mux test suite |
| [`doc/user_manual.md`](file:///e:/python%20audio%20noise%20reduction/doc/user_manual.md) | End-user installation guide, quickstart walkthrough, parameter tuning guide, and troubleshooting FAQ |
| [`doc/project_documentation.md`](file:///e:/python%20audio%20noise%20reduction/doc/project_documentation.md) | Project roadmap, module responsibility breakdown, contribution conventions, and release milestones |

---

## 3. Directory Layout & Code Organization

All source code and test implementations must strictly follow this structure:

```text
python-audio-noise-reduction/
│
├── AGENTS.md                       # AI Agent Operating Guidelines (this document)
├── README.md                       # High-level overview & quickstart guide
├── requirements.txt                # Python runtime dependencies
├── pyproject.toml                  # Packaging and tool configurations
├── run.bat / run.ps1 / run.sh      # One-click startup scripts
│
├── doc/                            # Authoritative specification documents
│   ├── system_architecture.md      # Pipeline diagrams & subsystem architecture
│   ├── feature_specifications.md   # Functional specs & parameter definitions
│   ├── tech_stack_and_engine.md    # DSP engine, libraries, & FFmpeg integration
│   ├── ui_ux_design.md             # UI wireframes, color palette, & components
│   ├── testing_and_verification.md # Test fixtures, synthetic SNR benchmarks
│   ├── user_manual.md              # User instructions & troubleshooting
│   └── project_documentation.md    # Project overview, milestones, & changelog
│
├── src/
│   ├── __init__.py
│   ├── main.py                     # GUI Application entry point
│   │
│   ├── core/                       # Decoupled processing engines (Headless / No GUI dependencies)
│   │   ├── __init__.py
│   │   ├── audio_engine.py         # Spectral gating, stationary & non-stationary noise reduction
│   │   ├── video_engine.py         # FFmpeg audio extraction & stream-copy remuxing
│   │   ├── filter_pipeline.py      # High-pass, low-pass, notch, noise gate, peak limiter, normalizer
│   │   └── audio_analyzer.py       # Waveform downsampling, RMS energy, and SNR estimation
│   │
│   ├── gui/                        # Presentation layer (View & Controllers)
│   │   ├── __init__.py
│   │   ├── app.py                  # Main Window, sidebar navigation, & layout
│   │   ├── theme.py                # Styling tokens, fonts, dark-mode color scheme
│   │   ├── components/             # Reusable UI widgets
│   │   │   ├── __init__.py
│   │   │   ├── drop_zone.py        # Drag-and-drop media import zone
│   │   │   ├── waveform_widget.py  # Interactive Before/After audio waveform display
│   │   │   ├── player_controls.py  # Play/Pause, scrubber, A/B switch, volume slider
│   │   │   ├── settings_panel.py   # Denoise parameters, algorithm presets, advanced toggles
│   │   │   └── batch_queue_view.py # Multi-file queue list with progress bars & status chips
│   │
│   └── utils/                      # Shared helper utilities
│       ├── __init__.py
│       ├── ffmpeg_helper.py        # Automatic FFmpeg binary detection & validation
│       ├── audio_io.py             # Audio file loading, slicing, format conversion, & export
│       ├── logger.py               # Rotating logging setup and debug reporting
│       └── temp_manager.py         # Safe temporary directory manager with automatic cleanup
│
└── tests/                          # Automated unit, integration, and benchmark tests
    ├── __init__.py
    ├── conftest.py                 # Pytest fixtures and synthetic noise generators
    ├── test_audio_engine.py        # DSP noise reduction validation & SNR improvement tests
    ├── test_video_engine.py        # Video demux/remux lossless validation tests
    ├── test_filter_pipeline.py     # Filter unit tests (highpass, lowpass, limiter)
    └── test_ffmpeg_helper.py       # FFmpeg binary discovery and command builder tests
```

---

## 4. Coding Standards & Agent Rules

1. **Decoupled Architecture**: All core DSP and video processing logic in `src/core/` must be 100% headless and executable from CLI/scripts without importing any GUI libraries.
2. **Non-Blocking UI Thread**: Never perform file I/O, audio decoding, noise suppression, or FFmpeg subprocesses on the main GUI thread. Use `threading.Thread` or `concurrent.futures.ThreadPoolExecutor` with thread-safe UI callback events.
3. **Strict Type Annotations**: Use Python 3.10+ type hints on every function and class method (`numpy.ndarray`, `pathlib.Path`, `typing.Callable`, `typing.Optional`).
4. **Clean Resource Management**: Always handle temporary audio extractions using `tempfile` / `temp_manager.py` and ensure files are deleted even if exceptions occur.
5. **Lossless Video Remuxing**: When processing video files, never re-encode video frames. Always use stream copy (`-c:v copy`) to preserve 100% original video clarity and complete muxing in seconds.
6. **No Placeholders**: When writing code, provide complete, robust implementations with proper try-except error handling and logging.

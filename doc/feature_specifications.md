# Feature Specifications — Audio & Video Noise Reduction Software

> **Status**: Approved Specifications  
> **Document Version**: 1.0.0  
> **Target Audience**: Developers, AI Agents, Quality Assurance

---

## 1. Feature Epics Overview

The software delivers four core functional Epics:

```mermaid
mindmap
  root((Noise Reduction Software))
    EPIC-1: Unified Media Import
      Audio Containers: WAV, MP3, FLAC, AAC, M4A, OGG
      Video Containers: MP4, MKV, MOV, AVI, WEBM
      Drag-and-Drop Dropzone
      Metadata & Track Length Detection
    EPIC-2: Advanced DSP Denoising Engine
      Stationary Spectral Gating
      Non-Stationary Adaptive Filtering
      High-Pass & Low-Pass Roll-Off
      Noise Gate & Peak Limiter
      Auto-Normalization Target
    EPIC-3: Interactive Visual & Audio Preview
      Dual Before / After Waveforms
      Synchronized Audio Scrubber
      Instant A/B Audio Switcher
      Zoom & Pan Waveform Canvas
      Estimated SNR dB Improvement
    EPIC-4: Batch Processing & Export
      Multi-File Queue
      Lossless Video Stream Remuxing
      Custom Output Format & Bitrate
      Custom Suffix / Directory Output
```

---

## 2. Detailed Epic & Feature Specifications

### EPIC-1: Unified Media Import & Analysis

| Feature ID | Feature Name | Description | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **FEAT-101** | Drag-and-Drop Import | User drops single or multiple files onto the UI dropzone. | - Accepts valid extensions (`.wav`, `.mp3`, `.flac`, `.aac`, `.m4a`, `.ogg`, `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`).<br>- Highlights drop zone on hover.<br>- Rejects unsupported formats with friendly modal error. |
| **FEAT-102** | Video Audio Extraction | If a video file is detected, automatically extract audio stream to high-fidelity temporary WAV. | - Extracts full uncompressed 16-bit / 24-bit PCM at original sample rate.<br>- Extracts in under 2 seconds for a 1-hour video.<br>- Preserves multi-channel (Stereo/5.1) layout. |
| **FEAT-103** | Audio Metadata Parsing | Inspect file duration, sample rate, channels, codec, bit depth, and file size. | - Displays metadata badge in the UI (e.g., `48.0 kHz | Stereo | 03:42 | MP4`). |

---

### EPIC-2: DSP Noise Reduction Controls & Parameters

The user can customize the noise reduction pipeline using intuitive presets ("Mild Hiss", "Aggressive Fan/AC", "Outdoor Wind/Urban", "Voice Podcast Clear") or fine-tune individual DSP sliders:

```mermaid
flowchart LR
    subgraph Parameter_Controls ["DSP Parameter Matrix"]
        P1["Reduction Strength\n(0.0 to 1.0 / 0dB to -40dB)"]
        P2["Mode\n(Stationary vs Non-Stationary)"]
        P3["High-Pass Cutoff\n(Off / 40Hz / 80Hz / 120Hz)"]
        P4["Low-Pass Cutoff\n(Off / 8kHz / 12kHz / 16kHz)"]
        P5["Time Smoothing\n(1 to 10 Frames)"]
        P6["Noise Gate Threshold\n(-60dB to -20dB)"]
        P7["Normalize Output\n(Off / -1.0 dBFS / -14 LUFS)"]
    end
```

#### Parameter Reference Table:

| Parameter Name | Data Type | Default Value | Valid Range | Function & DSP Impact |
| :--- | :--- | :--- | :--- | :--- |
| `reduction_strength` | `float` | `0.80` (80%) | `0.10` – `1.00` | Controls the gain multiplier applied to frequency bins identified as noise. Higher values remove more noise but may introduce slight phase artifacts. |
| `stationary_mode` | `bool` | `True` | `True` / `False` | `True`: Assumes consistent background noise (fans, hums). Fast and clean.<br>`False`: Continuously tracks changing noise floors (wind, city streets). |
| `high_pass_hz` | `int` | `80` Hz | `0` – `300` Hz | Butterworth high-pass filter to eliminate sub-bass rumble, microphone handling thumps, and electrical AC hum (50Hz/60Hz). `0` disables filter. |
| `low_pass_hz` | `int` | `0` (Off) | `0` – `20000` Hz | Filters out ultra-high frequency hiss above vocal range. |
| `time_smoothing` | `int` | `3` | `1` – `10` | Temporal smoothing across STFT time frames. Eliminates "musical chirping" artifacts. |
| `noise_gate_db` | `float` | `0.0` (Off) | `-70.0` – `-10.0` dB | Hard/Soft gate to silence residual noise during pauses between speech. |
| `normalize` | `bool` | `True` | `True` / `False` | Peak normalizes denoised audio to `-1.0 dBFS` to restore optimal listening volume. |

---

### EPIC-3: Interactive Visual & Audio Preview

| Feature ID | Feature Name | Description | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **FEAT-301** | Dual Waveform Display | Shows top waveform (Original Dirty Signal in Red/Amber) and bottom waveform (Denoised Signal in Emerald/Cyan). | - Downsampled 60 FPS responsive render.<br>- Shows amplitude envelope clearly.<br>- Visual playhead bar moves synchronously with audio. |
| **FEAT-302** | Instant A/B Toggle | User can switch between Original and Clean audio seamlessly while playback is active. | - Gapless audio switching (< 5ms switch latency).<br>- Visual indicator switches between `[A: Original]` and `[B: Clean]`. |
| **FEAT-303** | SNR Metric Display | Displays estimated Signal-to-Noise Ratio before and after processing. | - Displays badge (e.g., `Original: 12.4 dB SNR → Clean: 28.1 dB SNR (+15.7 dB)`). |

---

### EPIC-4: Batch Processing & Export Engine

```mermaid
sequenceDiagram
    autonumber
    participant UI as Batch Manager
    participant Q as Batch Queue
    participant Engine as Export Pipeline
    participant Disk as Local Storage

    UI->>Q: Enqueue 5 Media Files
    loop For Each File in Queue
        Q->>Engine: Process File (Audio or Video)
        Engine->>Engine: Apply Denoising & Filtering
        alt File is Video
            Engine->>Disk: Remux with stream-copy -> "[filename]_denoised.mp4"
        else File is Audio
            Engine->>Disk: Export selected format (WAV/MP3/FLAC) -> "[filename]_denoised.wav"
        end
        Engine-->>UI: Update Row Progress (100% - Done)
    end
    UI-->>UI: Show "All 5 Files Processed Successfully" notification
```

#### Output Naming & Directory Options:
- **Default Output Mode**: Save in the same directory with customizable suffix (e.g., `interview_cleaned.mp4`).
- **Custom Directory Mode**: Save all outputs to a specified folder (e.g., `D:\Cleaned_Media\`).
- **Export Formats (for Audio)**:
  - `WAV` (16-bit, 24-bit, 32-bit float PCM)
  - `MP3` (128 kbps, 192 kbps, 256 kbps, 320 kbps VBR/CBR)
  - `FLAC` (Lossless 24-bit)
- **Export Formats (for Video)**:
  - Original Container (`.mp4`, `.mkv`, `.mov`) with video stream-copy (`-c:v copy`) and AAC / FLAC audio track.

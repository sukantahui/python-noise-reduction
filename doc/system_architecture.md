# System Architecture — Audio & Video Noise Reduction Software

> **Status**: Approved Architectural Blueprint  
> **Software Category**: Cross-Platform Desktop Audio & Video Denoising GUI  
> **Target Python Version**: Python 3.10+

---

## 1. High-Level System Architecture

The application is architected around a strict **Three-Tier Modular Design** separating the Presentation Layer (GUI), the Core Signal & Video Processing Engines (Headless DSP), and the I/O / Platform Utilities.

```mermaid
flowchart TB
    subgraph UI_Layer ["Presentation Layer (CustomTkinter / PySide6 GUI)"]
        MAIN_WIN["Main Application Window\n(Navigation, Dark Theme)"]
        DROP_ZONE["Drag-and-Drop Media Import Zone"]
        SETTINGS["DSP Parameter Sliders & Presets Panel"]
        WAVE_WIDGET["Before / After Waveform & Spectrogram Canvas"]
        PLAYER_BAR["Audio Scrubber, Play/Pause, A/B Toggle"]
        BATCH_VIEW["Batch Queue & Export Progress Modal"]
    end

    subgraph Thread_Controller ["Async / Background Worker Subsystem"]
        WORKER_POOL["ThreadPoolExecutor / Worker Threads"]
        TASK_QUEUE["Processing Task Queue"]
        PROGRESS_DISPATCHER["Thread-Safe UI Progress & Status Events"]
    end

    subgraph Core_Engines ["Core Processing Subsystems (Headless Engine)"]
        AUDIO_ENG["Audio Denoising Engine\n(Stationary & Non-Stationary Spectral Gating)"]
        FILTER_PIPE["Filter Pipeline\n(High-Pass, Low-Pass, DC Notch, Gate, Limiter)"]
        VIDEO_ENG["Video Remuxing Engine\n(FFmpeg Demux, Audio Extraction, Stream-Copy Mux)"]
        ANALYZER["Audio Signal Analyzer\n(RMS, Peak, SNR Estimation, Waveform Downsampler)"]
    end

    subgraph Utilities_IO ["I/O & Platform Subsystem"]
        FFMPEG_WRAP["FFmpeg Binary Detector & Subprocess Manager"]
        AUDIO_IO["Soundfile / Librosa Audio File Handler"]
        TEMP_MGR["Safe Temp File & Workspace Manager"]
        LOGGER["Structured Rotating Logger"]
    end

    %% Event & Data Flows
    DROP_ZONE -->|"Media File Selected"| TASK_QUEUE
    SETTINGS -->|"DSP Parameters"| TASK_QUEUE
    TASK_QUEUE --> WORKER_POOL
    WORKER_POOL -->|"Dispatch Audio Job"| AUDIO_ENG
    WORKER_POOL -->|"Dispatch Video Job"| VIDEO_ENG
    
    VIDEO_ENG -->|"1. Extract Audio"| FFMPEG_WRAP
    FFMPEG_WRAP -->|"Raw Temp WAV"| AUDIO_IO
    AUDIO_IO -->|"NumPy Array (Float32)"| FILTER_PIPE
    FILTER_PIPE -->|"Filtered Array"| AUDIO_ENG
    AUDIO_ENG -->|"Denoised Array"| ANALYZER
    
    ANALYZER -->|"Waveform Samples"| PROGRESS_DISPATCHER
    PROGRESS_DISPATCHER -->|"Update Waveform"| WAVE_WIDGET
    PROGRESS_DISPATCHER -->|"Update Progress %"| BATCH_VIEW
    
    AUDIO_ENG -->|"Clean Audio Array"| AUDIO_IO
    AUDIO_IO -->|"Temp Clean WAV"| VIDEO_ENG
    VIDEO_ENG -->|"2. Stream-Copy Mux"| FFMPEG_WRAP
    FFMPEG_WRAP -->|"Output Clean Video File"| UI_Layer
```

---

## 2. Subsystem Breakdown & Component Architecture

### 2.1. Audio Denoising Subsystem (`src/core/audio_engine.py`)
The Audio Engine operates directly on floating-point multi-channel or mono NumPy arrays (`np.ndarray` of dtype `np.float32`, shape `(channels, samples)`):

```mermaid
flowchart LR
    INPUT[Input Audio Array\nFloat32] --> PRE_FILTER[Pre-Filter:\nHigh-Pass 80Hz / DC Offset]
    PRE_FILTER --> PROFILE_DETECT{Noise Profile Mode}
    
    PROFILE_DETECT -- "Auto / Stationary" --> STAT_GATE[Stationary Spectral Gating\nFFT Analysis over Initial/Quiet Frames]
    PROFILE_DETECT -- "Non-Stationary" --> ADAPT_GATE[Non-Stationary Time-Varying Filter\nRolling Spectral Floor Calculation]
    PROFILE_DETECT -- "Manual Noise Sample" --> SAMPLE_GATE[Spectral Gating using\nUser-Selected Noise Slice]
    
    STAT_GATE --> POST_LIMITER[Post-Processing:\nSoft Knee Limiter + Normalization]
    ADAPT_GATE --> POST_LIMITER
    SAMPLE_GATE --> POST_LIMITER
    
    POST_LIMITER --> OUTPUT[Clean Audio Array\nFloat32]
```

#### Key Algorithms & Math:
- **Spectral Gating**: Converts audio to Short-Time Fourier Transform (STFT). For each frequency bin $f$ and time frame $t$, the magnitude $|X(t,f)|$ is compared against a noise threshold $\Theta(f)$.
- **Masking Gain**: Multiplies spectral magnitude by gain mask $G(t, f) = \max\left(1 - \frac{\alpha \cdot \Theta(f)}{|X(t,f)|}, 1 - \text{reduction\_strength}\right)$.
- **Time Smoothing**: Consecutive masks are smoothed across time windows to eliminate "musical noise" (random isolated spectral peaks).

---

### 2.2. Video Processing & Stream-Copy Engine (`src/core/video_engine.py`)

When a user supplies a video file, the software never performs expensive video transcoding. Instead, it extracts the audio track, applies DSP noise suppression, and remuxes the audio into the original container using FFmpeg stream copy.

```mermaid
sequenceDiagram
    autonumber
    participant UI as GUI Controller
    participant Worker as Background Worker Thread
    participant VideoEng as Video Engine (Python)
    participant FFmpeg as FFmpeg Binary
    participant AudioEng as Audio DSP Engine

    UI->>Worker: User requests denoise for "interview.mp4"
    Worker->>VideoEng: Extract audio track
    VideoEng->>FFmpeg: ffmpeg -i interview.mp4 -vn -acodec pcm_s16le -ar 48000 temp_audio.wav
    FFmpeg-->>VideoEng: Extraction Complete (temp_audio.wav)
    
    VideoEng->>AudioEng: Denoise temp_audio.wav -> clean_audio.wav
    AudioEng-->>VideoEng: Denoising Finished
    
    VideoEng->>FFmpeg: ffmpeg -i interview.mp4 -i clean_audio.wav -c:v copy -c:a aac -b:a 320k -map 0:v:0 -map 1:a:0 output_clean.mp4
    FFmpeg-->>VideoEng: Lossless Remux Finished (< 3 seconds)
    
    VideoEng-->>Worker: Output file path ready
    Worker-->>UI: Update GUI: Complete & Enable Playback / Open Folder
```

#### FFmpeg Command Rules:
1. **Extraction**: `ffmpeg -y -i "{input_video}" -vn -acodec pcm_s16le -ar {sample_rate} "{temp_wav}"`
2. **Remuxing (MP4/MKV/MOV)**: `ffmpeg -y -i "{input_video}" -i "{clean_wav}" -c:v copy -c:a aac -b:a 320k -map 0:v:0 -map 1:a:0 -shortest "{output_video}"`
3. **Lossless Remuxing (FLAC/PCM in MKV)**: `ffmpeg -y -i "{input_video}" -i "{clean_wav}" -c:v copy -c:a flac -map 0:v:0 -map 1:a:0 "{output_video}"`

---

### 2.3. Threading & Concurrency Model

To maintain 60 FPS UI responsiveness on Windows/macOS/Linux, all computationally intensive tasks are strictly offloaded from the Tkinter/Qt main event loop:

- **GUI Main Thread**: Handles user clicks, slider drags, UI redraws, waveform canvas animations.
- **Worker Thread Pool (`ThreadPoolExecutor(max_workers=N)`)**:
  - Worker 1: Audio loading and FFT decomposition.
  - Worker 2: Spectral gating and inverse STFT synthesis.
  - Worker 3: FFmpeg extraction and remuxing child processes.
- **Inter-Thread Communication**: Thread-safe queues (`queue.Queue`) and custom events dispatch progress callbacks (`update_progress(percent: float, message: str)`) to the GUI thread via thread-safe UI scheduling.

---

### 2.4. Audio Signal Analyzer & Waveform Rendering (`src/core/audio_analyzer.py`)

Waveforms with millions of audio samples cannot be rendered in real-time on UI canvases without optimization.
- **Peak Min-Max Downsampling**: Downsamples a 10,000,000-sample audio array to exact canvas pixel width (e.g., 800 to 1200 points) by computing $(\min, \max)$ envelopes for each pixel bucket.
- **SNR Estimation**: Computes estimated Signal-to-Noise Ratio (in dB) using root-mean-square energy difference between speech activity frames and background silence frames:
  $$\text{SNR}_{\text{dB}} = 10 \cdot \log_{10}\left(\frac{P_{\text{signal}}}{P_{\text{noise}}}\right)$$
- **Spectrogram Generation**: Optional 2D Mel-Spectrogram matrix computation for visual inspection of frequency energy before and after filtering.

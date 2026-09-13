# PRIVACY68

### **Privacy-Preserving Edge-Native Voice Automation Architecture with Dual-Lane Semantic Routing and Quantized Transformer ASR**

### **Abstract**
Privacy68 is an ultra-low latency, 100% private, on-device artificial intelligence voice assistant and desktop automation framework engineered to provide seamless operating system control without cloud dependency. The proposed architecture addresses critical limitations of conventional cloud-tethered voice assistants, including persistent network latency, telemetry surveillance, subscription costs, and external data leakage. The real-time audio pipeline integrates an acoustic keyword spotting engine, a neural Voice Activity Detection (Silero VAD) buffer, and a local GPU-accelerated faster-whisper (CTranslate2) Automatic Speech Recognition (ASR) model operating in float16 precision with automatic int8 CPU quantization fallback. For command comprehension, Privacy68 implements a novel Dual-Lane Semantic Decision Engine: a fast-lane vectorizer leverages Term Frequency-Inverse Document Frequency (TF-IDF) representation and cosine similarity thresholding across pre-indexed skill intents to resolve routine desktop commands deterministically in under 2 milliseconds, while complex, unstructured, or ambiguous requests dynamically route to an on-device Large Language Model (Qwen 2.5 via Ollama) for zero-shot natural language reasoning and contextual tool selection. System extensibility is achieved through a decoupled plugin microkernel supporting runtime hot-reloading and isolated user-level customization stored in AppData. A non-intrusive presentation tier features a transparent floating Heads-Up Display (HUD) overlay, Windows notification tray integration, and a comprehensive hardware diagnostic suite that verifies local CUDA runtimes, GPU memory, audio input streams, and LLM availability. The overall objective is to deliver a computationally efficient, fully autonomous, and verifiable zero-cloud voice interaction environment for desktop computing.

### **Keywords**
Voice Assistant; Privacy68; Edge AI; On-Device Machine Learning; Automatic Speech Recognition; faster-whisper; Dual-Lane Semantic Routing; TF-IDF Vectorization; Large Language Model; Ollama; Qwen 2.5; Desktop Automation; CTranslate2; Privacy-Preserving Computing; Windows OS.

### **Tools:**
* **Front-End / UI:** Tkinter Floating HUD Overlay, Pystray System Tray Daemon, HTML5/CSS3/JavaScript (Control Center & Web Portal)
* **Back-End & Core Pipeline:** Python 3.11+, Multithreaded Audio Streamer, SoundDevice, NumPy, PyWin32
* **Acoustic Keyword Spotting:** openWakeWord, ONNX Runtime (80ms frame evaluation)
* **Speech Recognition (ASR):** faster-whisper, CTranslate2 (CUDA float16 GPU acceleration & int8 CPU fallback)
* **Fast-Lane Semantic Routing:** Scikit-Learn (TF-IDF Vectorizer, Cosine Similarity Matrix)
* **Natural Language Reasoning:** Ollama Local Server, Qwen 2.5 (0.5B / 1.5B Quantized LLM)
* **OS & Application Automation:** Windows Win32 API, ctypes Virtual-Key Codes, Subprocess Native IPC
* **Packaging & Distribution:** PyInstaller (CArchive/OneDir Bundler), Inno Setup Compiler 7.x

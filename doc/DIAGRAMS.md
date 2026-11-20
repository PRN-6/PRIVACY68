# PRIVACY68 // SYSTEM ARCHITECTURE & DATA FLOW DIAGRAMS

This document contains the complete visual diagram specifications for **PRIVACY68** (Version 1.7.3). All diagrams use standard Mermaid syntax suitable for documentation, Overleaf LaTeX rendering, and presentation slides.

---

## 1. End-to-End System Architecture Diagram

```mermaid
flowchart TD
    subgraph Ingestion["1. User Interaction & Ingestion Layer"]
        QCB["Quick Command Bar<br/>(Ctrl+Alt+Space • Tkinter)"]
        TG["Telegram Remote Gateway<br/>(Voice Notes & Text • Cellular 4G/5G)"]
        DASH["Control Center Dashboard<br/>(pywebview • Chromium Edge)"]
        TRAY["Windows Notification Tray<br/>(pystray Background Residency)"]
    end

    subgraph AudioPipeline["2. Acoustic Normalization & Speech Layer"]
        AVDEC["In-Memory Audio Decoder<br/>(PyAV / OGG-to-PCM • 16kHz Float32)"]
        NORM["Acoustic Normalizer<br/>(DC-Bias Removal • Peak Norm 0.95 • 60ms Pad)"]
        WISP["Faster-Whisper Neural Model<br/>(Local CPU INT8 Quantization)"]
        GSR["Google Web Speech API<br/>(Free Cloud Fallback Engine)"]
    end

    subgraph SecurityDispatch["3. Security Normalization & Router Layer"]
        AUTOCORR["Lexical Autocorrector<br/>(autocorrect_speech_command)"]
        ROUTER["Action Executor & Router<br/>(actions/executor.py)"]
        FASTPATH{"Learned Skill Exists?<br/>(actions/skill_manager.py)"}
        SKILLREC["0ms Fast-Path Execution<br/>(Zero API Tokens / Instant Recall)"]
    end

    subgraph AIEngine["4. Intelligence & Cascading LLM Brain"]
        BRAIN["Agent Brain Orchestrator<br/>(actions/agent_brain.py)"]
        SKILLREG["OpenClaw Skill Registry<br/>(SKILL.md Dynamic Manifests)"]
        CASCADE{"LiteLLM Cascading Router"}
        GEMINI["Tier 1: Google Gemini 3.1 Flash-Lite<br/>(Default Primary Brain)"]
        GROQ["Tier 2: Groq LPU Llama-3.3 70B<br/>(Ultra-Fast Failover)"]
        CLAUDE["Tier 3: Anthropic Claude 3.5 Sonnet<br/>(Complex Multi-Step Reasoning)"]
        OPENAI["Tier 4: OpenAI GPT-4o-mini<br/>(Reliable Script Fallback)"]
        OLLAMA["Tier 5: Local Ollama Qwen2.5<br/>(100% Air-Gapped Offline)"]
    end

    subgraph Execution["5. Isolated Execution & Self-Healing Engine"]
        RUNNER["Subprocess Agent Runner<br/>(actions/agent_runner.py)"]
        SELFHEAL{"Script Error?<br/>(returncode != 0)"}
        REPAIR["Self-Healing Reflection Loop<br/>(Injects Traceback & Repairs Code)"]
    end

    subgraph WindowsServices["6. Native Windows Operating Services"]
        SYS["System Controller<br/>(services/system.py)<br/>• Virtual Desktops 1-10<br/>• Fast-Path Close App<br/>• Volume, Battery, Screenshot"]
        APPS["Fuzzy App Launcher<br/>(services/apps.py)"]
        GMAIL["Gmail Compose Controller<br/>(services/gmail.py)"]
        SKILLS["OpenClaw Extensible Skills<br/>(skills/git, github, docker, etc.)"]
    end

    subgraph Vault["7. Security Enclave & Local State"]
        DPAPI[("Windows Credential Manager<br/>DPAPI Encrypted Vault")]
        PROFILE[("profile.json<br/>User Configuration Database")]
    end

    %% Ingestion flows
    QCB -->|Typed Command| AUTOCORR
    DASH -->|Console Input| ROUTER
    TG -->|Audio Bytes .ogg| AVDEC
    TG -->|Text Message| AUTOCORR
    AVDEC --> NORM
    NORM --> WISP
    NORM -.->|Optional Online| GSR
    WISP -->|Transcribed Text| AUTOCORR
    GSR -.->|Transcribed Text| AUTOCORR

    %% Dispatch flows
    AUTOCORR --> ROUTER
    ROUTER --> FASTPATH
    FASTPATH -->|Yes: Exact Match| SKILLREC
    SKILLREC --> SYS
    FASTPATH -->|No: New Command| BRAIN

    %% AI Brain flows
    SKILLREG -.->|Inject Schemas| BRAIN
    BRAIN --> CASCADE
    CASCADE -->|Primary| GEMINI
    CASCADE -.->|Failover 1| GROQ
    CASCADE -.->|Failover 2| CLAUDE
    CASCADE -.->|Failover 3| OPENAI
    CASCADE -.->|Offline| OLLAMA

    %% Execution flows
    GEMINI -->|Synthesized Python| RUNNER
    GROQ -->|Synthesized Python| RUNNER
    CLAUDE -->|Synthesized Python| RUNNER
    OPENAI -->|Synthesized Python| RUNNER
    OLLAMA -->|Synthesized Python| RUNNER

    RUNNER --> SELFHEAL
    SELFHEAL -->|Exit Code != 0| REPAIR
    REPAIR -->|Corrected Script| RUNNER
    SELFHEAL -->|Success: Code 0| SYS
    SELFHEAL -->|Success: Code 0| APPS
    SELFHEAL -->|Success: Code 0| GMAIL
    SELFHEAL -->|Success: Code 0| SKILLS

    %% Feedback to user
    SYS -->|Status / Screenshot| TG
    SYS -->|Display Output| QCB
    SYS -->|Live Metrics| DASH

    %% Vault bindings
    DPAPI <-->|API Keys & PAT Tokens| BRAIN
    PROFILE <-->|Pairing PIN & Preferences| ROUTER
```

---

## 2. Data Flow Diagram (DFD Level 0 & Level 1)

### DFD Level 0: Context Diagram
```mermaid
flowchart LR
    UserLocal["Local User<br/>(Workstation)"]
    UserRemote["Remote User<br/>(Mobile Phone)"]
    P68System(("PRIVACY68<br/>Autonomous Core"))
    WinOS["Microsoft Windows OS<br/>(Apps, Virtual Desktops, Audio, Files)"]
    CloudAI["Cloud AI Providers<br/>(Gemini, Groq, Claude, OpenAI)"]
    TGApi["Telegram Bot API<br/>(Encrypted Cloud Gateway)"]

    UserLocal -->|"Typed Commands<br/>(Ctrl+Alt+Space)"| P68System
    P68System -->|"Execution Status & Output"| UserLocal

    UserRemote -->|"Voice Notes & Commands"| TGApi
    TGApi -->|"Encrypted In-Memory Audio"| P68System
    P68System -->|"Replies, Screenshots & Status"| TGApi
    TGApi -->|"Mobile Notifications"| UserRemote

    P68System -->|"Prompts & Context"| CloudAI
    CloudAI -->|"Python Automation Scripts"| P68System

    P68System -->|"Process, Keyboard & Window Calls"| WinOS
    WinOS -->|"System Telemetry & Metrics"| P68System
```

---

## 3. Runtime Sequence & Self-Healing Decision Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Telegram / Command Bar)
    participant Exec as Action Executor (actions/executor.py)
    participant SM as Skill Manager (Learned Skills)
    participant Brain as Agent Brain (actions/agent_brain.py)
    participant Cloud as Cloud AI (Gemini 3.1 / Groq)
    participant Runner as Subprocess Runner (actions/agent_runner.py)
    participant OS as Windows OS Subsystems

    User->>Exec: Submit command ("Show git status" or "Switch to Desktop 2")
    Exec->>Exec: Clean vocal tics & conversational prefixes
    Exec->>SM: Check Learned Skills library (0ms Fast-Path)
    
    alt Skill Already Learned
        SM-->>Exec: Return cached executable script
        Exec->>OS: Execute native procedural action
        OS-->>Exec: Return live stdout output
        Exec-->>User: Display instant output (0ms latency, 0 API tokens)
    else New Natural-Language Request
        Exec->>Brain: Dispatch to Agent Brain
        Brain->>Cloud: Prompt with OpenClaw skills context
        alt Primary Provider Succeeds
            Cloud-->>Brain: Return synthesized Python script
        else Primary Provider 429 Rate Limit
            Brain->>Cloud: Failover to Groq LPU / Claude
            Cloud-->>Brain: Return synthesized Python script
        end
        Brain->>Runner: Execute script in isolated subprocess
        Runner->>OS: Execute OS operations
        OS-->>Runner: Return exit code & stdout/stderr
        
        alt Execution Success (returncode == 0)
            Runner-->>Brain: Script completed successfully
            Brain->>SM: Crystallize new working skill for future 0ms recall
            Brain-->>Exec: Return execution output
            Exec-->>User: Return success message & desktop screenshot
        else Execution Failure (returncode != 0)
            Runner-->>Brain: Return stderr traceback
            Brain->>Cloud: Self-Healing Prompt (error context + failed code)
            Cloud-->>Brain: Return repaired Python script
            Brain->>Runner: Re-execute repaired script
            Runner->>OS: Execute repaired OS calls
            OS-->>Runner: Success
            Runner-->>Brain: Repaired output
            Brain-->>Exec: Return repaired output
            Exec-->>User: Return verified result
        end
    end
```

---

## 4. Privacy & Zero-Mic Hardware Isolation Model

```mermaid
flowchart TD
    subgraph Traditional["Commercial Assistants (Siri / Alexa / Cortana)"]
        MIC1["PC Microphone Hardware"] -->|"Continuous Audio Polling (100% Active)"| STREAM1["Background Audio Ring Buffer"]
        STREAM1 -->|"Wake Word Detection ('Hey Siri')"| CLOUD1["Vendor Cloud Infrastructure"]
        STREAM1 -.->|"High False Acceptance Rate (FAR)"| LEAK["Acoustic Telemetry & Privacy Leakage"]
    end

    subgraph Privacy68Model["PRIVACY68 Privacy Architecture"]
        MIC2["PC Microphone Hardware"] ---|"HARDWARE UNBOUND & PERMANENTLY CLOSED"| OFF["Zero Audio Buffer • Zero Mic Access"]
        PHONE["User Mobile Phone (Telegram)"] -->|"Deliberate Voice Note (User Pressed Record)"| ENCR["Telegram Bot API (TLS Encrypted)"]
        ENCR -->|"In-Memory OGG Audio Bytes"| RAM["Host PC Process Memory (RAM)"]
        RAM -->|"PyAV In-Memory Decode (Zero Disk Writes)"| WHISP["Faster-Whisper INT8 (On-Device Local CPU)"]
        WHISP -->|"Text Command String"| EXECUTE["Action Execution Engine"]
    end
```

---

*Authored by PRN-6 // PRIVACY68 Architecture & Data Flow Reference*

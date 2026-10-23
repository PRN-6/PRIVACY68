# Software Design Specification (SDS): PRIVACY68

## 1. Introduction
### 1.1 Purpose
The purpose of this document is to provide a detailed design specification for the PRIVACY68 system. PRIVACY68 is an intelligent, voice-driven automation framework designed to provide low-latency, secure, and privacy-centric control over the Windows operating system.

### 1.2 Scope
The system encompasses speech-to-text processing, an advanced multi-lane command routing engine, a plugin-based skill manager, and a secure execution layer that interacts with the Windows Win32 API and various third-party application APIs.

### 1.3 Definitions, Acronyms, and Abbreviations
| Term | Definition |
| :--- | :--- |
| **SDS** | Software Design Specification |
| **LLM** | Large Language Model |
| **Fast Lane** | Deterministic routing path (<5ms latency, zero LLM) |
| **API Lane** | Cloud-assisted semantic routing path |
| **LLM Lane** | Local, air-gapped model routing path |
| **Security Guard** | The system's confirmation and authorization interceptor |

---

## 2. System Architecture
### 2.1 High-Level Architecture
PRIVACY68 utilizes a layered architecture to separate input processing, command routing, and system execution.

**Data Flow:**
`Voice Input` $\rightarrow$ `Autocorrect/Cleaning` $\rightarrow$ `Security Guard` $\rightarrow$ `Routing Engine (3 Lanes)` $\rightarrow$ `Skill Manager` $\rightarrow$ `Windows OS / APIs`

### 2.2 The Three-Lane Command Architecture
To solve the trade-off between AI flexibility and execution speed, PRIVACY68 implements a tiered routing strategy:

#### 2.2.1 Lane 1: Fast Lane (Highest Priority)
*   **Mechanism:** Exact keyword lookups, pre-compiled RegEx, and a lightweight ML Intent Classifier (TF-IDF + Logistic Regression).
*   **Goal:** Instant response (<5ms).
*   **Use Case:** Volume control, locking the PC, opening common apps (Chrome, Notepad), and basic system settings.

#### 2.2.2 Lane 2: API Lane (High Priority)
*   **Mechanism:** Cloud-based semantic routers and direct Application Programming Interfaces (APIs).
*   **Goal:** High accuracy and reliability across different hardware profiles.
*   **Use Case:** Complex web queries, cloud-integrated app controls, and semantic intent matching.

#### 2.2.3 Lane 3: Local LLM Lane (Optional)
*   **Mechanism:** Local Ollama models running in an air-gapped environment.
*   **Goal:** Maximum privacy and complex reasoning without external data transmission.
*   **Use Case:** Private data manipulation, complex local file operations, and custom local plugins.

---

## 3. Detailed Design
### 3.1 Command Execution Pipeline (`executor.py`)
The `ActionExecutor` manages the lifecycle of a command:
1.  **Preprocessing:** Cleans speech artifacts via `autocorrect_speech_command`.
2.  **Security Check:** Intercepts sensitive actions through the `security_guard`.
3.  **Macro Expansion:** Checks the `macro_engine` for predefined workflows (e.g., "Coding Mode").
4.  **Compound Planning:** Uses the `command_planner` to split multi-clause utterances (e.g., "Mute volume AND open Chrome").
5.  **Sequential Routing:** Attempts execution in order: **Fast Lane $\rightarrow$ API Lane $\rightarrow$ LLM Lane**.

### 3.2 Security Model
The system employs a 3-Tier Security Model to prevent accidental or unauthorized system changes:
*   **Level 1 (Low):** Instant execution for non-destructive tasks.
*   **Level 2 (Medium):** Requires a "Confirm/Yes" voice prompt for sensitive tasks.
*   **Level 3 (High):** Full authorization required for system-critical changes.

### 3.3 Plugin & Skill Management
The `skill_manager` allows the system to be extended without modifying the core engine. Each plugin defines:
*   **Fast Intents:** O(1) dictionary mappings for instant routing.
*   **Pattern Intents:** RegEx patterns for flexible phrasing.
*   **Execution Logic:** The actual Python code that interacts with the OS.

---

## 4. Technical Specifications
### 4.1 Technology Stack
*   **Language:** Python 3.x
*   **OS Target:** Windows 10/11 (Win32 API)
*   **ML Models:** TF-IDF / Logistic Regression (Fast Lane), Ollama (Local LLM)
*   **Interfacing:** `computer_use` library for system input/output control.

### 4.2 Performance Targets
| Metric | Target | Lane |
| :--- | :--- | :--- |
| **Routing Latency** | < 5ms | Fast Lane |
| **Routing Latency** | < 200ms | API Lane |
| **Routing Latency** | Variable (Hardware Dep.) | LLM Lane |
| **Accuracy** | > 98% | Deterministic Actions |

---

## 5. Appendices
### 5.1 Component Map
*   `actions/fast_lane.py`: Implements the high-speed ML router.
*   `actions/executor.py`: The central orchestration engine.
*   `computer_use/security_guard.py`: Handles the confirmation logic.
*   `computer_use/context_inspector.py`: Retrieves system state (RAM, CPU, Battery).

# System Design Report: PRIVACY68

## 1. SYSTEM DESIGN

### 1.1 Architectural Design
PRIVACY68 is a sophisticated system automation framework developed to provide low-latency, secure, and privacy-centric control over the Windows operating system via voice commands. The system combines high-speed deterministic routing with cloud-based tool calling and local LLM capabilities, allowing users to automate OS tasks, manage system settings, and execute complex workflows without compromising their privacy.

The application is developed using Python and leverages the Win32 API for deep operating system integration. It employs a unique "Three-Lane Architecture" to handle commands based on their complexity and required latency. The system manages three primary levels of interaction: low-level system shortcuts, mid-level API-driven application controls, and high-level local LLM reasoning.

When a user provides a voice command, the system processes it through an autocorrection layer and then passes it to the Routing Engine. Depending on the intent, the command is routed through one of three paths:
1. **Fast Lane:** Uses high-speed deterministic keyword mapping for near-instant execution (<5ms).
2. **API Lane:** Utilizes cloud-based semantic routers for high-reliability application control through function calling.
3. **Local LLM Lane:** Employs an air-gapped local model (via Ollama) for complex, private reasoning tasks.

The overall design connects a voice-processing front-end, a secure execution guard, and a plugin-based skill manager so that system automation, security, and extensibility work together as one seamless ecosystem.

The overall design connects a voice-processing front-end, a secure execution guard, and a plugin-based skill manager so that system automation, security, and extensibility work together as one seamless ecosystem.

#### 1.1.2 Command Routing Architecture
The routing architecture explains how user commands are classified and how the system decides which "lane" to use for execution to balance speed and intelligence.

Instead of a static training pipeline, PRIVACY68 uses a tiered dispatch system:
1. **Deterministic Path (Fast Lane):** High-frequency "reflex" commands (like volume or locking the PC) are matched using high-speed keyword lookups. This ensures near-instant response times (<5ms) without any LLM overhead.
2. **Semantic Path (API Lane):** For all other commands, the system utilizes a "Tool-Use" architecture. The request is sent to a Cloud LLM along with a JSON menu of available tools. The LLM reasons about the user's intent and returns a structured tool call (e.g., `open_app("chrome")`).
3. **Private Path (Local LLM Lane):** For sensitive tasks, the system uses a local Ollama model to ensure data never leaves the machine.

This architecture eliminates the need for manual training datasets and allows the system to handle a vast range of natural language commands without requiring exact phrasing.

## 2. DETAILED DESIGN

### 2.1 Tool and Intent Design
The core of PRIVACY68's intelligence is its Tool-Use architecture, which allows the agent to map natural language to specific system functions without requiring exact keyword matching.

Instead of relying on a fixed dataset, the system uses a dynamic registry of tools. Each tool is defined by a JSON schema that includes its name, description, and required parameters.

#### 2.1.1 Tool Provenance and Registry
The tool registry is built from the active plugins installed in the system. Each plugin provides a set of functions that the agent can call. This modular approach allows the agent to expand its capabilities simply by adding new plugins.

#### 2.1.2 Tool Schema and Definition
The system uses a standardized schema to communicate with the LLM. This ensures that the agent knows exactly how to call a function.

| Field | Type | Description |
| :--- | :--- | :--- |
| **Function Name** | Text | The unique identifier for the tool (e.g., `open_application`). |
| **Description** | Text | A natural language explanation of what the tool does. |
| **Parameters** | Object | The inputs required (e.g., `app_name` as a string). |
| **Return Type** | Text | The expected output of the function. |

#### 2.1.3 Target / Label Definition
The target of the routing engine is to map a user's utterance to the correct function call. The primary function categories include:
1. **open_application**: Launching software like Chrome, VS Code, or Notepad.
2. **open_folder**: Navigating to specific Windows directories.
3. **open_settings**: Opening specific Windows Control Panel or Settings pages.
4. **system_action**: Triggering OS-level events like locking the PC or muting volume.
5. **type_text**: Dictating text to be typed into the active window.

#### 2.1.4 Semantic Mapping and Generalization
By using a Cloud LLM for tool selection, the system achieves "zero-shot" generalization. This means the user can phrase a command in any way—"Get me Chrome," "I need the browser," or "Start the web app"—and the LLM will correctly map it to the `open_application("chrome")` tool based on the function's description.

### 2.2 Preprocessing and Routing
Preprocessing ensures that input is clean before it reaches the routing engine.

#### 2.2.1 Validation and Cleaning
Every command undergoes a preprocessing pipeline:
*   **Autocorrection:** Speech-to-text errors are corrected via `autocorrect_speech_command`.
*   **Normalization:** Text is converted to lowercase and stripped of trailing punctuation.
*   **Validation:** Empty or corrupted inputs are rejected immediately to avoid unnecessary API calls.

#### 2.2.2 Routing Strategy
PRIVACY68 uses a prioritized routing strategy:
1. **Fast Lane Match:** The system first checks for "reflex" keywords. If a match is found, it executes instantly.
2. **Semantic Tool Selection:** If no reflex match is found, the request is sent to the LLM with the tool menu. The LLM selects the best tool.
3. **Local Fallback:** If cloud access is unavailable or the task is private, the local LLM is used for reasoning.

### 2.3 Tool-Use Architecture
The system uses a highly optimized routing architecture to ensure zero-perceivable latency for common tasks while maintaining high intelligence for complex ones.

#### 2.3.1 The Deterministic Fast Lane
The Fast Lane handles "reflex" actions. Instead of a heavy model, it uses high-speed keyword matching and deterministic routing. This allows the system to execute the most common OS commands in <5ms, making the voice assistant feel instantaneous.

#### 2.3.2 Semantic Tool Selection (The API Lane)
For all non-reflex tasks, the system employs **Function Calling**. The user's request is sent to a Cloud LLM alongside a JSON menu of available tools. The LLM reasons about the user's intent and returns a structured tool call. 

**Reason for this Architecture:**
Unlike a trained ML model, which is limited to the phrases it saw during training, this approach allows the agent to understand any way a user might phrase a request. It provides the flexibility of a full LLM with the precision of a coded function.

#### 2.3.3 Model Architecture
The model architecture describes the path from a voice utterance to a system action.

**Diagram Description:**
`Voice Input` $\rightarrow$ `Text Cleaning` $\rightarrow$ `Keyword Check (Fast Lane)` $\rightarrow$ `Semantic Router (API Lane)` $\rightarrow$ `Tool Call` $\rightarrow$ `Skill Manager` $\rightarrow$ `Win32 API Call`.

The system first attempts the Fast Lane for speed. If no match is found, it uses the API Lane to semantically map the request to a tool. The selected tool is then executed by the Skill Manager.


## 2.4 Database and Storage Design
Unlike a traditional data-driven app, PRIVACY68 is an execution-driven framework. It prioritizes real-time system state and configuration over persistent relational records.

The system uses a decentralized storage architecture to ensure speed and privacy:
1.  **Model Storage:** The trained ML weights (`intent_model.pkl` and `param_model.pkl`) are stored as binary files for instant loading into memory.
2.  **Plugin Configuration:** Plugin metadata and fast-intent maps are stored in Python modules and configuration files, allowing for O(1) lookup times.
3.  **System State:** Real-time data (RAM usage, CPU load, Battery status) is not stored in a database but is retrieved dynamically via the `context_inspector` using Windows API calls.

#### 2.4.1 Storage Architecture
The storage architecture focuses on the flow between the saved ML models, the plugin registry, and the Windows OS environment.

**Architecture Description:**
*   **Static Storage:** Holds the `.pkl` model weights and the `speaker_model.onnx` for voice synthesis.
*   **Plugin Registry:** A dynamic map of available skills and their respective execution requirements.
*   **OS Interface:** The primary "data source" where the system reads the current active window, clipboard content, and system resource metrics.

#### 2.4.2 Schema
Since PRIVACY68 is an execution-driven framework rather than a record-keeping application, it uses a a mixture of binary model storage and dynamic system hooks rather than a traditional relational database.

| Storage Component | Purpose |
| :--- | :--- |
| **intent_model.pkl** | Stores the trained Logistic Regression weights for command classification. |
| **param_model.pkl** | Stores the TF-IDF vectorizer state for consistent text-to-vector conversion. |
| **speaker_model.onnx** | Stores the neural network weights for voice synthesis/TTS. |
| **plugin_manager** | A dynamic registry storing the mapping of intents to Python function calls. |
| **Win32 API Hooks** | Dynamic access points for retrieving system state (CPU, RAM, Battery). |

The system avoids persistent user databases to maintain a zero-footprint privacy model, ensuring that user commands are processed in memory and not logged to a permanent local database.

## 2.5 UML and Behavioral Design
This section explains how the user interacts with the system and how the internal routing engine responds to different command types.

#### 2.5.1 Use Case Diagram
The use-case diagram identifies the main activities performed by the user interacting with the PRIVACY68 voice assistant.

**User (Operator):**
*   **Basic Automation:** Mutes/unmutes audio, locks the computer, and manages window states (maximize/minimize).
*   **Application Control:** Launches specific software (e.g., "Open Chrome") or navigates to specific folders.
*   **System Diagnostics:** Requests real-time system health (e.g., "What is using my RAM?").
*   **Developer Workflow:** Executes Git commands (status, push, commit) and opens projects in VS Code via voice.
*   **Complex Tasking:** Issues compound commands (e.g., "Mute the volume and open GitHub") and interacts with the Security Guard for sensitive actions.

The system provides a seamless experience by routing these various activities through the appropriate lane (Fast, API, or LLM) based on the complexity and security level of the requested action.

#### 2.5.2 Component Diagram
The component diagram describes the internal structural dependencies of the PRIVACY68 framework.

The voice interface provides the user input, while the **Action Executor** processes the requests. The **Fast Lane, API Lane, and Local LLM Lane** act as the core processing engines, working together with the **Skill Manager** to generate the final system action.

This diagram represents the main software components and their dependencies—such as the connection between the `FastLaneRouter` and the `computer_use` system tools—rather than separate classes, ensuring it reflects the actual architectural flow of the source code.

#### 2.5.3 Sequence Diagram
The sequence diagram explains the order of operations when a user issues a voice command.

**Sequence Flow:**
1. **User** $\rightarrow$ speaks command $\rightarrow$ **Speech-to-Text**.
2. **Speech-to-Text** $\rightarrow$ cleaned text $\rightarrow$ **Action Executor**.
3. **Action Executor** $\rightarrow$ checks $\rightarrow$ **Security Guard** (if sensitive).
4. **Action Executor** $\rightarrow$ routes to $\rightarrow$ **Fast/API/LLM Lane**.
5. **Lane** $\rightarrow$ triggers $\rightarrow$ **Skill Manager/Plugin**.
6. **Plugin** $\rightarrow$ executes $\rightarrow$ **Windows OS API**.
7. **Windows OS** $\rightarrow$ returns result $\rightarrow$ **User Notification**.

When a user issues a command, the voice interface captures the audio and sends the transcribed text to the **Action Executor**. The executor validates the input and checks for security risks via the **Security Guard** before routing the command to the most efficient lane. The selected lane then invokes the specific skill or plugin, which interacts with the Windows API to perform the action. The result is then returned to the user as a status notification.

#### 2.5.4 Activity Diagram
The activity diagram shows the steps followed during command execution, including the error handling process when a command is unrecognized or blocked.

**Activity Flow:**
1. **Input Capture:** Receive voice/text input.
2. **Preprocessing:** Autocorrect and clean text.
3. **Security Check:** If a sensitive action is detected, prompt for voice confirmation.
    *   *If Denied:* Stop execution and notify the user.
    *   *If Confirmed:* Proceed to routing.
4. **Routing Phase:**
    *   Attempt **Fast Lane** (Deterministic).
    *   If not handled, attempt **API Lane** (Semantic).
    *   If not handled, attempt **LLM Lane** (Reasoning).
5. **Execution:** Execute the matched skill/plugin via the OS bridge.
6. **Error Handling:** If no lane handles the command, trigger the "Unrecognized Command" fallback and provide guidance to the user.
7. **Completion:** Send "Success" or "Error" feedback to the UI.

The process starts when the user issues a voice or text command. The system first checks if the input is valid and non-empty. If the command is corrupted or empty, an error message is displayed. Otherwise, the input is cleaned and routed through the three-lane architecture. If the command is recognized, the final action is performed on the OS, and the success status and confidence score (for ML-routed commands) are displayed to the user.

## 2.6 User Interface Design
The user interface is designed to make the system's control features intuitive and accessible. Because PRIVACY68 is primarily a voice-driven background service, the UI focuses on status feedback and configuration rather than traditional page navigation.

The main user interface components include:
*   **Status Overlay:** A lightweight notification system that displays whether a command was successfully executed or if an error occurred.
*   **Command Console:** A text-based interface for users to type commands and view the routing path (e.g., "Executed via Fast Lane").
*   **Settings Dashboard:** A configuration area where users can enable/disable the Local LLM Lane, manage active plugins, and set security levels for sensitive actions.
*   **System Health Monitor:** A visual display of the information retrieved by the `context_inspector` (CPU, RAM, and Battery).

---

## 3. REFERENCES
1. A.J. Institute of Engineering & Technology, Department of MCA, Software Design Specification (SDS) Format for Machine Learning Projects.
2. Python Documentation: https://docs.python.org/3/
3. Win32 API Documentation: https://learn.microsoft.com/en-us/windows/win32/
4. Ollama Documentation: https://ollama.com/library
5. Scikit-Learn Documentation (TF-IDF & Logistic Regression): https://scikit-learn.org/stable/
6. PRIVACY68 Project Source Code and Internal Documentation.








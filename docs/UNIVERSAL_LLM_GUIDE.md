# PRIVACY68 Universal LLM & API Integration Guide

This guide explains how to connect **any cloud AI API key** (Google Gemini, Groq, OpenRouter, Anthropic Claude, OpenAI, DeepSeek, Mistral) or **any local offline LLM** (Ollama, LM Studio, LocalAI, Jan, vLLM) to PRIVACY68.

---

## Architecture Overview

PRIVACY68 is engineered to be **provider-agnostic**. It does not lock you into a single proprietary AI model or require costly GPU hardware. You can freely switch between:

1. **Free Cloud APIs** (Google Gemini, Groq LPU, OpenRouter) with zero credit card required.
2. **Commercial Frontier APIs** (Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o).
3. **100% Offline Local LLMs** (Ollama, LM Studio, vLLM) for zero-internet execution.
4. **Custom OpenAI-Compatible Endpoints** (DeepSeek, Mistral, Together AI, or remote private VPS).

```
                      PRIVACY68 UNIVERSAL AI ORCHESTRATION
                      
                          ┌──────────────────────────┐
                          │   Natural Language User  │
                          │     Voice/Text Input     │
                          └────────────┬─────────────┘
                                       │
                        Fast-Path Skill Match (>= 0.75)?
                                       │
                      ┌────────────────┴────────────────┐
                      │ YES                             │ NO
                      ▼                                 ▼
             [Learned Skill (0ms)]             [Universal Agent Brain]
             (skills.json - 0 tokens)          (LiteLLM Dynamic Routing)
                                                        │
                      ┌─────────────────────────────────┼──────────────────────────────┐
                      ▼                                 ▼                              ▼
             [Free Cloud APIs]                 [Offline Local LLMs]            [Custom Endpoints]
             • Gemini 3.5 Flash                • Ollama (qwen2.5-coder)        • LM Studio (localhost:1234)
             • Groq LPU (GPT-OSS 120B)         • Local Llama 3.2               • DeepSeek / Mistral
             • OpenRouter (100+ free)          • Remote Ollama Host            • LocalAI / vLLM / Jan
                      │                                 │                              │
                      └─────────────────────────────────┴──────────────────────────────┘
                                                        │
                                                        ▼
                                          [Intra-Provider Auto-Failover]
                                          (Tries sibling models on 404/429)
                                                        │
                                                        ▼
                                          [3-Tier Security Inspection]
                                          (Safe / Sensitive / Blocked)
                                                        │
                                                        ▼
                                          [Subprocess Self-Healing Loop]
                                          (Fixes code autonomously on stderr)
```

---

## 1. Free Cloud AI Providers (Recommended)

### A. Google Gemini API (Ultra-Fast & Generous Free Tier)
* **Website**: [Google AI Studio](https://aistudio.google.com/app/apikey)
* **Cost**: 100% Free daily tier (No credit card needed).
* **Recommended Model**: `gemini/gemini-3.5-flash`
* **Setup in Dashboard**:
  1. Open the **AI Brain (APIs)** tab.
  2. Paste your Gemini API key (starts with `AIzaSy...` or `AQ.Ab...`) into the **Google Gemini API** slot.
  3. Click **Save Key** (PRIVACY68 auto-activates `gemini/gemini-3.5-flash`).
* **Active Working Models**:
  - `gemini/gemini-3.5-flash` (Recommended)
  - `gemini/gemini-flash-latest`
  - `gemini/gemini-2.5-flash`
  - `gemini/gemini-2.0-flash`

---

### B. Groq Cloud (Ultra-Fast LPU Inference ~200ms)
* **Website**: [Groq Console](https://console.groq.com/keys)
* **Cost**: 100% Free daily tier (No credit card needed).
* **Recommended Model**: `groq/openai/gpt-oss-120b` or `groq/qwen/qwen3.8-27b`
* **Setup in Dashboard**:
  1. Open the **AI Brain (APIs)** tab.
  2. Paste your Groq API key (starts with `gsk_...`) into the **Groq Cloud API** slot.
  3. Click **Save Key** (PRIVACY68 auto-activates `groq/openai/gpt-oss-120b`).
* **Active Working Models**:
  - `groq/openai/gpt-oss-120b` (Ultra-fast code generation)
  - `groq/openai/gpt-oss-20b`
  - `groq/qwen/qwen3.8-27b`

---

### C. OpenRouter (100+ Free Models from Top Labs)
* **Website**: [OpenRouter Keys](https://openrouter.ai/keys)
* **Cost**: 100+ models ending in `:free` are completely free.
* **Recommended Model**: `openrouter/google/gemini-2.0-flash-exp:free` or `openrouter/meta-llama/llama-3.3-70b-instruct:free`
* **Setup in Dashboard**:
  1. Open the **AI Brain (APIs)** tab.
  2. Paste your OpenRouter API key (starts with `sk-or-v1-...`) into the **OpenRouter API** slot.
  3. Click **Save Key**.
* **Active Free Models**:
  - `openrouter/google/gemini-2.0-flash-exp:free`
  - `openrouter/meta-llama/llama-3.3-70b-instruct:free`
  - `openrouter/mistralai/mistral-small-24b-instruct-2501:free`

---

## 2. 100% Offline Local LLMs (Zero Cloud, Zero Internet)

### A. Ollama (Recommended Local Engine)
* **Website**: [ollama.com/download](https://ollama.com/download)
* **Installation**: Download and install the official Windows `.exe`.
* **Recommended Models**:
  - High Performance Coding: `ollama pull qwen2.5-coder:7b`
  - General Purpose: `ollama pull llama3.2:latest`
  - Ultra-Lightweight (Runs on any low-end PC, only 397MB): `ollama pull qwen2.5:0.5b`
* **Dashboard Integration**:
  1. When Ollama is running, PRIVACY68 automatically detects all installed models and displays them as **clickable chips** in the **Ollama & Local LLMs** card.
  2. Click any model chip (e.g. `qwen2.5-coder:7b`) to immediately set it as your active reasoning brain.
  3. If running Ollama on another computer on your home network, enter its address (e.g., `http://192.168.1.50:11434`) and click **Save Endpoint**.

---

### B. LM Studio / LocalAI / Jan / vLLM (Custom Local Servers)
If you prefer running models through LM Studio or LocalAI:

1. Launch your local server in LM Studio (default address: `http://localhost:1234/v1`).
2. In the PRIVACY68 dashboard under **OpenAI & Custom Endpoints**:
   - In **Custom Base URL**, enter: `http://localhost:1234/v1`
   - In **API Key**, enter any dummy text (e.g. `lm-studio`) or leave empty.
   - Click **Save Base URL**.
3. In **Active LLM Model Identifier**, type your loaded model name prefixed with `openai/` (e.g., `openai/qwen2.5-coder-7b-instruct`).
4. Click **Apply Model**. PRIVACY68 will now execute all reasoning against your local LM Studio server!

---

## 3. Commercial Frontier APIs

### Anthropic Claude
* **Key Format**: `sk-ant-...`
* **Recommended Model**: `claude-3-5-sonnet-20241022` or `claude-3-5-haiku-20241022`
* **Features**: Frontier reasoning and complex multi-step Windows automation.

### OpenAI
* **Key Format**: `sk-proj-...` or `sk-...`
* **Recommended Model**: `openai/gpt-4o-mini` or `openai/gpt-4o`

### DeepSeek / Mistral / Together AI
* Enter your API key and custom base URL in the **OpenAI & Custom Endpoints** card:
  - DeepSeek: Base URL `https://api.deepseek.com/v1`, Model: `openai/deepseek-chat`
  - Mistral: Base URL `https://api.mistral.ai/v1`, Model: `openai/mistral-small-latest`

---

## 4. Multi-Provider Auto-Failover & Intra-Provider Cascading

One of PRIVACY68's greatest strengths is **continuous reliability**. If an individual model encounters rate limits (HTTP 429) or is decommissioned (HTTP 404):

```
                       CASCADING FAILOVER ORDER
                       
  [Primary Model (e.g. Groq Llama 3.3)] ───► Failed (404 Not Found)
                    │
                    ▼
  [Same-Provider Candidate 1] ─────────────► Try `groq/openai/gpt-oss-120b` (SUCCESS!)
                    │                         └─► Auto-heals `.env` model setting!
                    ▼ (If failed)
  [Same-Provider Candidate 2] ─────────────► Try `groq/qwen/qwen3.8-27b`
                    │
                    ▼ (If all Groq failed)
  [Cross-Provider Fallback 1] ─────────────► Try `gemini/gemini-3.5-flash`
                    │
                    ▼
  [Cross-Provider Fallback 2] ─────────────► Try `openrouter/google/gemini-2.0-flash-exp:free`
                    │
                    ▼
  [Cross-Provider Fallback 3] ─────────────► Try `claude-3-5-sonnet-20241022`
                    │
                    ▼
  [Offline Local Fallback] ────────────────► Try `ollama/qwen2.5-coder:7b`
```

### Self-Healing Configuration
When a fallback model succeeds, PRIVACY68 updates `AGENT_BRAIN_MODEL` in your `.env` file automatically. You will never experience failover delay on subsequent runs.

---

## 5. Complete Environment Variables Reference (`.env`)

You can edit these settings directly in the Dashboard UI or in your `.env` file:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `AGENT_BRAIN_MODEL` | `gemini/gemini-3.5-flash` | The active LLM identifier used for Python code generation. |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini API key from Google AI Studio. |
| `GROQ_API_KEY` | *(empty)* | Groq Cloud API key from console.groq.com. |
| `OPENROUTER_API_KEY` | *(empty)* | OpenRouter API key for 100+ free models. |
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic Claude API key (`sk-ant-...`). |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key (`sk-...`). |
| `OPENAI_API_BASE` | *(empty)* | Custom Base URL for OpenAI-compatible endpoints (LM Studio, LocalAI, DeepSeek). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Address of your local or remote Ollama server. |
| `OLLAMA_API_KEY` | *(empty)* | Optional authentication token for protected remote Ollama instances. |
| `AGENT_BRAIN_MAX_RETRIES` | `2` | Number of autonomous self-healing retries upon Python execution error. |

---

## 6. Frequently Asked Questions (FAQ)

### Q: Do I need a credit card to use PRIVACY68?
**No.** Google Gemini, Groq Cloud, and OpenRouter all offer generous 100% free daily tiers without requiring any credit card details. Local Ollama is completely free and runs offline.

### Q: Will my API keys be transmitted anywhere?
**No.** All API keys are stored exclusively on your local computer in your `.env` file. They are never sent to any telemetry server or external service other than the direct AI provider API endpoint you configured.

### Q: How do I know if PRIVACY68 is using my local model or cloud API?
The Live Console in the dashboard explicitly prints the provider used for each command (e.g., `Reasoning via gemini/gemini-3.5-flash` or `Running learned skill ... (0ms fast-path)`).

### Q: Can I run PRIVACY68 completely offline without internet?
**Yes.** Once you install Ollama and pull a local model (such as `qwen2.5-coder:7b`), set your active model to `ollama/qwen2.5-coder:7b`. Additionally, all learned skills in `skills.json` run completely offline without internet.


"""
PRIVACY68 Control Center - Modern CustomTkinter Native Desktop GUI
Pure Python, zero-browser / zero-WebView2 dependency. Works on any computer.
"""

import os
import sys
import threading
import subprocess
import time
import urllib.request
from typing import Optional

import customtkinter as ctk

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
from actions.agent_brain import is_ollama_online, agent_brain
from actions.executor import execute_system_command_detailed


# Theme setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Color palette
COLOR_BG_DARK = "#0F1117"
COLOR_SIDEBAR = "#161922"
COLOR_CARD = "#1E222D"
COLOR_CARD_HOVER = "#262C3A"
COLOR_ACCENT_RED = "#E50914"
COLOR_ACCENT_RED_HOVER = "#B80710"
COLOR_ACCENT_BLUE = "#3B82F6"
COLOR_ACCENT_GREEN = "#10B981"
COLOR_TEXT_PRIMARY = "#F3F4F6"
COLOR_TEXT_MUTED = "#9CA3AF"
COLOR_CODE_BG = "#111827"


class Privacy68Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PRIVACY68 Control Center - Smart Assistant")
        self.geometry("1000x640")
        self.minsize(840, 500)
        self.configure(fg_color=COLOR_BG_DARK)

        # State
        self.streamer = None
        self.streamer_thread = None
        self.is_listening = False
        self.active_tab = "console"

        # Build UI layout
        self._build_layout()

        # Initial background checks
        self.after(500, self._check_services)

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Left Navigation Sidebar ──
        self.sidebar = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)

        # Brand header
        brand_label = ctk.CTkLabel(
            self.sidebar,
            text="PRIVACY 68",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_ACCENT_RED
        )
        brand_label.grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="AI Desktop Assistant",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        subtitle.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # Nav Buttons
        self.nav_console_btn = ctk.CTkButton(
            self.sidebar,
            text="💻 Live Console",
            anchor="w",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLOR_ACCENT_RED,
            hover_color=COLOR_ACCENT_RED_HOVER,
            command=lambda: self._switch_tab("console")
        )
        self.nav_console_btn.grid(row=2, column=0, padx=12, pady=3, sticky="ew")

        self.nav_brain_btn = ctk.CTkButton(
            self.sidebar,
            text="🧠 AI Brain (APIs)",
            anchor="w",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color=COLOR_CARD_HOVER,
            command=lambda: self._switch_tab("brain")
        )
        self.nav_brain_btn.grid(row=3, column=0, padx=12, pady=3, sticky="ew")

        self.nav_voice_btn = ctk.CTkButton(
            self.sidebar,
            text="🎙️ Voice & Audio",
            anchor="w",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color=COLOR_CARD_HOVER,
            command=lambda: self._switch_tab("voice")
        )
        self.nav_voice_btn.grid(row=4, column=0, padx=12, pady=3, sticky="ew")

        self.nav_settings_btn = ctk.CTkButton(
            self.sidebar,
            text="⚙️ Settings",
            anchor="w",
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color=COLOR_CARD_HOVER,
            command=lambda: self._switch_tab("settings")
        )
        self.nav_settings_btn.grid(row=5, column=0, padx=12, pady=3, sticky="ew")

        # Service Status Indicators
        status_frame = ctk.CTkFrame(self.sidebar, fg_color=COLOR_CARD, corner_radius=8)
        status_frame.grid(row=6, column=0, padx=12, pady=(12, 6), sticky="ew")

        self.voice_status_label = ctk.CTkLabel(
            status_frame,
            text="● Voice: Idle",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#F59E0B"
        )
        self.voice_status_label.pack(anchor="w", padx=10, pady=(6, 2))

        self.brain_status_label = ctk.CTkLabel(
            status_frame,
            text="● Brain: Checking...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.brain_status_label.pack(anchor="w", padx=10, pady=(0, 6))

        # Voice Streamer Toggle Button
        self.streamer_btn = ctk.CTkButton(
            self.sidebar,
            text="▶ Start Voice",
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLOR_ACCENT_GREEN,
            hover_color="#059669",
            command=self._toggle_voice_streamer
        )
        self.streamer_btn.grid(row=7, column=0, padx=12, pady=6, sticky="ew")

        # Footer
        footer_label = ctk.CTkLabel(
            self.sidebar,
            text="PRIVACY68 v2.0 • Pure Native",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLOR_TEXT_MUTED
        )
        footer_label.grid(row=9, column=0, padx=12, pady=10, sticky="s")

        # ── Main Content Area ──
        self.content_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_DARK, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Tab Frames container
        self.views = {}
        self._build_console_view()
        self._build_brain_view()
        self._build_voice_view()
        self._build_settings_view()

        self._switch_tab("console")

    # ── TAB 1: Console View ──
    def _build_console_view(self):
        view = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        # Top Stat Badges
        header_bar = ctk.CTkFrame(view, fg_color=COLOR_CARD, corner_radius=8, height=42)
        header_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        groq_active = bool(getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", ""))
        engine_name = "Groq Whisper (99%)" if groq_active else getattr(config, "SPEECH_ENGINE", "whispercpp")
        self.badge_engine = ctk.CTkLabel(
            header_bar,
            text=f"🎙️ Engine: {engine_name}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_BG_DARK,
            corner_radius=6,
            padx=10, pady=3
        )
        self.badge_engine.pack(side="left", padx=8, pady=6)

        wake_word = getattr(config, "WAKE_WORD_MODEL", "alexa")
        self.badge_wake = ctk.CTkLabel(
            header_bar,
            text=f"⚡ Wake: \"{wake_word}\"",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_BG_DARK,
            corner_radius=6,
            padx=10, pady=3
        )
        self.badge_wake.pack(side="left", padx=4, pady=6)

        self.clear_feed_btn = ctk.CTkButton(
            header_bar,
            text="Clear Log",
            width=70,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            hover_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT_MUTED,
            command=self._clear_feed
        )
        self.clear_feed_btn.pack(side="right", padx=8, pady=6)

        # Scrollable Feed Container
        self.feed_scroll = ctk.CTkScrollableFrame(view, fg_color=COLOR_CARD, corner_radius=8)
        self.feed_scroll.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        self.feed_scroll.grid_columnconfigure(0, weight=1)

        # Bottom Input Bar
        input_bar = ctk.CTkFrame(view, fg_color="transparent")
        input_bar.grid(row=2, column=0, sticky="ew")
        input_bar.grid_columnconfigure(0, weight=1)

        self.command_entry = ctk.CTkEntry(
            input_bar,
            placeholder_text="Type an instruction (e.g. 'open brave and search github', 'what time is it?')...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=40,
            corner_radius=8,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY
        )
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.command_entry.bind("<Return>", lambda e: self._send_manual_command())

        self.send_btn = ctk.CTkButton(
            input_bar,
            text="Execute",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=90,
            height=40,
            corner_radius=8,
            fg_color=COLOR_ACCENT_RED,
            hover_color=COLOR_ACCENT_RED_HOVER,
            command=self._send_manual_command
        )
        self.send_btn.grid(row=0, column=1)

        self.views["console"] = view

        # Initial welcome message in feed
        self._add_feed_card(
            title="PRIVACY68 Ready",
            body="Welcome to PRIVACY68 Control Center.\n• Type a command below or click 'Start Voice' in the sidebar to use wake word 'alexa'.\n• Built-in plugins: Chrome, Brave, WhatsApp, YouTube, Windows volume, screenshot, and files.",
            card_type="system"
        )

    # ── TAB 2: AI Brain View ──
    def _build_brain_view(self):
        view = ctk.CTkScrollableFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=8)
        view.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            view,
            text="Cloud & Web AI Brain (APIs Only)",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title.pack(anchor="w", padx=16, pady=(12, 4))

        desc = ctk.CTkLabel(
            view,
            text="PRIVACY68 operates 100% via AI APIs. No local LLM download, installation, or background daemon is required.\nSelect an API provider below (Groq [Free], Anthropic Claude, or a Remote Ollama Website URL).",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED,
            justify="left"
        )
        desc.pack(anchor="w", padx=16, pady=(0, 10))

        # Model configuration section
        model_frame = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        model_frame.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            model_frame,
            text="Active LLM Model:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 4))

        model_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        model_row.pack(fill="x", padx=14, pady=(0, 10))
        model_row.grid_columnconfigure(0, weight=1)

        self.brain_model_entry = ctk.CTkEntry(
            model_row,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY
        )
        self.brain_model_entry.insert(0, getattr(config, "AGENT_BRAIN_MODEL", "groq/llama-3.3-70b-versatile"))
        self.brain_model_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        save_model_btn = ctk.CTkButton(
            model_row,
            text="Apply Model",
            width=90,
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._apply_model_choice
        )
        save_model_btn.grid(row=0, column=1)

        # Quick Model Preset Dropdown
        preset_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        preset_row.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            preset_row,
            text="Model Presets:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="left", padx=(0, 8))

        self.preset_menu = ctk.CTkOptionMenu(
            preset_row,
            values=[
                "groq/llama-3.3-70b-versatile",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "openai/gpt-4o-mini",
                "ollama/llama3.2:latest",
                "ollama/qwen2.5-coder:7b"
            ],
            width=240,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_preset_selected
        )
        self.preset_menu.pack(side="left")

        # Groq Cloud API Frame (Free tier)
        groq_frame = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        groq_frame.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            groq_frame,
            text="⚡ Groq Cloud API (100% Free - LPU Powered Llama 3.3 70B)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            groq_frame,
            text="State-of-the-art 70B intelligence at ~200ms. Free daily API key at console.groq.com/keys (No card needed).",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 6))

        groq_key_row = ctk.CTkFrame(groq_frame, fg_color="transparent")
        groq_key_row.pack(fill="x", padx=14, pady=(0, 6))
        groq_key_row.grid_columnconfigure(0, weight=1)

        self.groq_brain_entry = ctk.CTkEntry(
            groq_key_row,
            placeholder_text="Paste Groq API Key (gsk_...)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER,
            show="•"
        )
        cur_groq = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        if cur_groq:
            self.groq_brain_entry.insert(0, cur_groq)
        self.groq_brain_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        save_groq_brain_btn = ctk.CTkButton(
            groq_key_row,
            text="Save Groq Key",
            width=120,
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._save_groq_brain_key
        )
        save_groq_brain_btn.grid(row=0, column=1)

        self.groq_brain_status_label = ctk.CTkLabel(
            groq_frame,
            text="● Status: " + ("Groq Cloud Active (Key Saved)" if cur_groq else "Inactive (Enter API key to activate)"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_ACCENT_GREEN if cur_groq else COLOR_TEXT_MUTED
        )
        self.groq_brain_status_label.pack(anchor="w", padx=14, pady=(0, 10))

        # Claude Cloud Intelligence Frame (Out of the Box / OpenClaw)
        claude_frame = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        claude_frame.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            claude_frame,
            text="⚡ Anthropic Claude AI (Out-of-the-Box / OpenClaw)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            claude_frame,
            text="Frontier reasoning with zero local model downloads. Works out of the box with Claude 3.5.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 6))

        claude_row = ctk.CTkFrame(claude_frame, fg_color="transparent")
        claude_row.pack(fill="x", padx=14, pady=(0, 6))
        claude_row.grid_columnconfigure(0, weight=1)

        self.claude_key_entry = ctk.CTkEntry(
            claude_row,
            placeholder_text="Paste Claude API Key (sk-ant-api03-...)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER,
            show="•"
        )
        cur_claude = getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        if cur_claude:
            self.claude_key_entry.insert(0, cur_claude)
        self.claude_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        save_claude_btn = ctk.CTkButton(
            claude_row,
            text="Save Claude Key",
            width=120,
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLOR_ACCENT_RED,
            hover_color=COLOR_ACCENT_RED_HOVER,
            command=self._save_claude_key
        )
        save_claude_btn.grid(row=0, column=1)

        self.claude_status_label = ctk.CTkLabel(
            claude_frame,
            text="● Status: " + ("Claude 3.5 Active (API Key Saved)" if cur_claude else "Inactive (Enter API key to activate)"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_ACCENT_GREEN if cur_claude else COLOR_TEXT_MUTED
        )
        self.claude_status_label.pack(anchor="w", padx=14, pady=(0, 10))

        # Ollama Controller Frame
        ctrl_frame = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        ctrl_frame.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            ctrl_frame,
            text="🌐 Ollama API (Local Service or Remote Cloud/Website):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            ctrl_frame,
            text="Connect to local Ollama (http://localhost:11434) or a remote Ollama server / website API URL.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 6))

        # Ollama URL Row
        url_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        url_row.pack(fill="x", padx=14, pady=(0, 6))
        url_row.grid_columnconfigure(0, weight=1)

        self.ollama_url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Ollama API URL (e.g. http://localhost:11434 or https://ollama.your-website.com)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER
        )
        cur_ollama_url = getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_url_entry.insert(0, cur_ollama_url)
        self.ollama_url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        save_ollama_btn = ctk.CTkButton(
            url_row,
            text="Save Ollama URL",
            width=120,
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._save_ollama_config
        )
        save_ollama_btn.grid(row=0, column=1)

        # Ollama Optional API Key Row
        key_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        key_row.pack(fill="x", padx=14, pady=(0, 8))
        key_row.grid_columnconfigure(0, weight=1)

        self.ollama_key_entry = ctk.CTkEntry(
            key_row,
            placeholder_text="Optional API Key / Bearer token (for cloud or secured Ollama website)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=30,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER,
            show="•"
        )
        cur_ollama_key = getattr(config, "OLLAMA_API_KEY", "") or os.environ.get("OLLAMA_API_KEY", "")
        if cur_ollama_key:
            self.ollama_key_entry.insert(0, cur_ollama_key)
        self.ollama_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.ollama_detail_label = ctk.CTkLabel(
            ctrl_frame,
            text="Status: Checking...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.ollama_detail_label.pack(anchor="w", padx=14, pady=(0, 6))

        btn_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_row.pack(anchor="w", padx=14, pady=(0, 10))

        check_btn = ctk.CTkButton(
            btn_row,
            text="Refresh Status",
            width=110,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._check_services
        )
        check_btn.pack(side="left", padx=(0, 8))

        start_ollama_btn = ctk.CTkButton(
            btn_row,
            text="Start Local Ollama",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLOR_ACCENT_BLUE,
            hover_color="#2563EB",
            command=self._launch_ollama_service
        )
        start_ollama_btn.pack(side="left")

        # Test reasoning frame
        test_frame = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        test_frame.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            test_frame,
            text="Test AI Reasoning Prompt:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.test_prompt_entry = ctk.CTkEntry(
            test_frame,
            placeholder_text="Enter test prompt (e.g. 'open notepad and type hello')...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER
        )
        self.test_prompt_entry.pack(fill="x", padx=14, pady=(0, 8))

        run_test_btn = ctk.CTkButton(
            test_frame,
            text="Test Brain Generation",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=COLOR_ACCENT_RED,
            hover_color=COLOR_ACCENT_RED_HOVER,
            command=self._test_brain_generation
        )
        run_test_btn.pack(anchor="w", padx=14, pady=(0, 10))

        self.views["brain"] = view

    # ── TAB 3: Voice View ──
    def _build_voice_view(self):
        view = ctk.CTkScrollableFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=8)
        view.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            view,
            text="Voice & Speech Settings",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title.pack(anchor="w", padx=16, pady=(12, 4))

        # Engine Selection
        box1 = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        box1.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            box1,
            text="Local Speech Engine:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.engine_selector = ctk.CTkOptionMenu(
            box1,
            values=["whispercpp (Fast CPU - Recommended)", "faster-whisper (CUDA/CPU)"],
            width=300,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_engine_changed
        )
        self.engine_selector.pack(anchor="w", padx=14, pady=(0, 10))

        # Groq Cloud Whisper Turbo Integration Box
        box_groq = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        box_groq.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            box_groq,
            text="⚡ Groq Cloud Whisper Turbo (~99% Accuracy, ~150ms)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            box_groq,
            text="Free tier on console.groq.com/keys (No credit card needed). State-of-the-art cloud model.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 6))

        groq_row = ctk.CTkFrame(box_groq, fg_color="transparent")
        groq_row.pack(fill="x", padx=14, pady=(0, 10))
        groq_row.grid_columnconfigure(0, weight=1)

        self.groq_key_entry = ctk.CTkEntry(
            groq_row,
            placeholder_text="Paste your Groq API Key (gsk_...)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            show="*",
            height=32,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_HOVER
        )
        cur_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        if cur_key:
            self.groq_key_entry.insert(0, cur_key)
        self.groq_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        save_key_btn = ctk.CTkButton(
            groq_row,
            text="Save Key",
            width=80,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._save_groq_key
        )
        save_key_btn.grid(row=0, column=1)

        self.groq_status_label = ctk.CTkLabel(
            box_groq,
            text="● Status: " + ("Groq Cloud Whisper Active (~99% accuracy)" if cur_key else "Inactive (Using Local CPU Whisper)"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_ACCENT_GREEN if cur_key else COLOR_TEXT_MUTED
        )
        self.groq_status_label.pack(anchor="w", padx=14, pady=(0, 10))

        # Wake Word Selection
        box2 = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        box2.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            box2,
            text="Wake Word:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.wake_selector = ctk.CTkOptionMenu(
            box2,
            values=["alexa", "jarvis", "privacy68", "nova"],
            width=180,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_wake_changed
        )
        self.wake_selector.pack(anchor="w", padx=14, pady=(0, 10))

        # Mic Test
        box3 = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        box3.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            box3,
            text="Microphone Test:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.mic_level_bar = ctk.CTkProgressBar(box3, width=280, height=12)
        self.mic_level_bar.set(0.0)
        self.mic_level_bar.pack(anchor="w", padx=14, pady=(4, 10))

        self.views["voice"] = view

    # ── TAB 4: Settings View ──
    def _build_settings_view(self):
        view = ctk.CTkScrollableFrame(self.content_frame, fg_color=COLOR_CARD, corner_radius=8)
        view.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            view,
            text="General Assistant Settings",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title.pack(anchor="w", padx=16, pady=(12, 4))

        info_frame = ctk.CTkFrame(view, fg_color=COLOR_BG_DARK, corner_radius=8)
        info_frame.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            info_frame,
            text="System Environment:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))

        paths = agent_brain._resolve_user_paths()
        env_text = (
            f"• User Home: {paths['home']}\n"
            f"• Desktop: {paths['desktop']}\n"
            f"• Downloads: {paths['downloads']}\n"
            f"• Remote Web Server: http://localhost:{getattr(config, 'REMOTE_SERVER_PORT', 8765)}"
        )
        ctk.CTkLabel(
            info_frame,
            text=env_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED,
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 10))

        self.views["settings"] = view

    # ── Tab Navigation ──
    def _switch_tab(self, tab_name: str):
        self.active_tab = tab_name
        for name, frame in self.views.items():
            if name == tab_name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        buttons = {
            "console": self.nav_console_btn,
            "brain": self.nav_brain_btn,
            "voice": self.nav_voice_btn,
            "settings": self.nav_settings_btn,
        }
        for name, btn in buttons.items():
            if name == tab_name:
                btn.configure(fg_color=COLOR_ACCENT_RED)
            else:
                btn.configure(fg_color="transparent")

    # ── Live Feed UI Card Helpers ──
    def _add_feed_card(self, title: str, body: str, card_type: str = "user", code: Optional[str] = None):
        card = ctk.CTkFrame(self.feed_scroll, fg_color=COLOR_BG_DARK, corner_radius=8)
        card.pack(fill="x", padx=8, pady=4)

        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(8, 2))

        color = COLOR_ACCENT_BLUE if card_type == "user" else (COLOR_ACCENT_RED if card_type == "code" else COLOR_TEXT_PRIMARY)
        icon = "👤 " if card_type == "user" else ("🤖 " if card_type == "assistant" else "⚙️ ")

        ctk.CTkLabel(
            header_frame,
            text=f"{icon}{title}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=color
        ).pack(side="left")

        time_str = time.strftime("%H:%M:%S")
        ctk.CTkLabel(
            header_frame,
            text=time_str,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(side="right")

        if body:
            ctk.CTkLabel(
                card,
                text=body,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLOR_TEXT_PRIMARY,
                justify="left",
                wraplength=640
            ).pack(anchor="w", padx=12, pady=(2, 6))

        if code:
            code_box = ctk.CTkTextbox(
                card,
                height=min(120, 20 + code.count("\n") * 16),
                font=ctk.CTkFont(family="Consolas", size=10),
                fg_color=COLOR_CODE_BG,
                text_color="#60A5FA",
                corner_radius=6
            )
            code_box.insert("1.0", code)
            code_box.configure(state="disabled")
            code_box.pack(fill="x", padx=10, pady=(0, 8))

    def _clear_feed(self):
        for widget in self.feed_scroll.winfo_children():
            widget.destroy()

    # ── Background Logic & Actions ──
    def _send_manual_command(self):
        cmd = self.command_entry.get().strip()
        if not cmd:
            return
        self.command_entry.delete(0, "end")

        self._add_feed_card("User Command", cmd, card_type="user")

        threading.Thread(target=self._execute_command_async, args=(cmd,), daemon=True).start()

    def _execute_command_async(self, cmd: str):
        try:
            result = execute_system_command_detailed(cmd)
            success = result.get("success", False)
            message = result.get("message", "")
            method = result.get("method", "system")
            code = getattr(agent_brain, "last_code", None)

            def update_ui():
                status_icon = "✅ " if success else "⚠️ "
                self._add_feed_card(
                    f"{status_icon}Execution Result ({method})",
                    message,
                    card_type="code" if code else "assistant",
                    code=code if code else None
                )

            self.after(0, update_ui)
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._add_feed_card("⚠️ Execution Error", err_msg, card_type="assistant"))

    def _check_services(self):
        def worker():
            ollama_ok = is_ollama_online()
            cur_model = getattr(config, "AGENT_BRAIN_MODEL", "ollama/llama3.2:latest").lower()
            claude_key = getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            groq_key = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")

            def update():
                # 1. Update Ollama service label with active endpoint
                ollama_url = getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
                if hasattr(self, "ollama_detail_label"):
                    if ollama_ok:
                        self.ollama_detail_label.configure(
                            text=f"Status: Online & Connected ({ollama_url})",
                            text_color=COLOR_ACCENT_GREEN
                        )
                    else:
                        self.ollama_detail_label.configure(
                            text=f"Status: Offline ({ollama_url} not reachable)",
                            text_color="#EF4444"
                        )

                # 2. Update Claude status label if available
                if hasattr(self, "claude_status_label"):
                    if claude_key:
                        self.claude_status_label.configure(
                            text="● Status: Claude 3.5 Active (API Key Saved)",
                            text_color=COLOR_ACCENT_GREEN
                        )
                    else:
                        self.claude_status_label.configure(
                            text="● Status: Inactive (Enter API key to activate)",
                            text_color=COLOR_TEXT_MUTED
                        )

                # 3. Update Groq brain status label if available
                if hasattr(self, "groq_brain_status_label"):
                    if groq_key:
                        self.groq_brain_status_label.configure(
                            text="● Status: Groq Cloud Active (Key Saved)",
                            text_color=COLOR_ACCENT_GREEN
                        )
                    else:
                        self.groq_brain_status_label.configure(
                            text="● Status: Inactive (Enter API key to activate)",
                            text_color=COLOR_TEXT_MUTED
                        )

                # 4. Update Left Sidebar Brain Status
                if "claude" in cur_model or "anthropic" in cur_model:
                    if claude_key:
                        self.brain_status_label.configure(text="● Brain: Online (Claude)", text_color=COLOR_ACCENT_GREEN)
                    else:
                        self.brain_status_label.configure(text="● Brain: Needs Claude Key", text_color="#F59E0B")
                elif "groq" in cur_model:
                    if groq_key:
                        self.brain_status_label.configure(text="● Brain: Online (Groq)", text_color=COLOR_ACCENT_GREEN)
                    else:
                        self.brain_status_label.configure(text="● Brain: Needs Groq Key", text_color="#F59E0B")
                else:
                    if ollama_ok:
                        self.brain_status_label.configure(text="● Brain: Online (Ollama)", text_color=COLOR_ACCENT_GREEN)
                    else:
                        self.brain_status_label.configure(text="● Brain: Ollama Offline", text_color="#EF4444")

            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    def _save_groq_brain_key(self):
        key = self.groq_brain_entry.get().strip()
        config.GROQ_API_KEY = key
        os.environ["GROQ_API_KEY"] = key
        if hasattr(self, "groq_key_entry"):
            self.groq_key_entry.delete(0, "end")
            self.groq_key_entry.insert(0, key)
        if key:
            if hasattr(self, "groq_brain_status_label"):
                self.groq_brain_status_label.configure(
                    text="● Status: Groq Cloud Active (Key Saved)",
                    text_color=COLOR_ACCENT_GREEN
                )
            self._add_feed_card(
                "Groq API",
                "Groq Cloud API key activated! Llama 3.3 70B cloud reasoning is ready (Free).",
                card_type="system"
            )
            if "ollama" in self.brain_model_entry.get():
                self.brain_model_entry.delete(0, "end")
                self.brain_model_entry.insert(0, "groq/llama-3.3-70b-versatile")
                self._apply_model_choice()
        else:
            if hasattr(self, "groq_brain_status_label"):
                self.groq_brain_status_label.configure(
                    text="● Status: Inactive (Enter API key to activate)",
                    text_color=COLOR_TEXT_MUTED
                )
            self._add_feed_card("Groq API", "Groq API key removed.", card_type="system")
        self._check_services()

    def _save_ollama_config(self):
        url = self.ollama_url_entry.get().strip() or "http://localhost:11434"
        key = self.ollama_key_entry.get().strip()
        config.OLLAMA_BASE_URL = url
        os.environ["OLLAMA_BASE_URL"] = url
        os.environ["OLLAMA_HOST"] = url
        os.environ["OLLAMA_API_BASE"] = url
        config.OLLAMA_API_KEY = key
        os.environ["OLLAMA_API_KEY"] = key
        self._add_feed_card("Ollama Config", f"Saved Ollama API endpoint: {url}", card_type="system")
        self._check_services()

    def _save_claude_key(self):
        key = self.claude_key_entry.get().strip()
        config.ANTHROPIC_API_KEY = key
        os.environ["ANTHROPIC_API_KEY"] = key
        if key:
            if hasattr(self, "claude_status_label"):
                self.claude_status_label.configure(
                    text="● Status: Claude 3.5 Active (API Key Saved)",
                    text_color=COLOR_ACCENT_GREEN
                )
            self._add_feed_card(
                "AI Brain",
                "Anthropic Claude API key activated! Out-of-the-box OpenClaw reasoning is now enabled.",
                card_type="system"
            )
            # If current model was still ollama, auto-switch to claude-3-5-sonnet
            if "ollama" in self.brain_model_entry.get():
                self.brain_model_entry.delete(0, "end")
                self.brain_model_entry.insert(0, "claude-3-5-sonnet-20241022")
                self._apply_model_choice()
        else:
            if hasattr(self, "claude_status_label"):
                self.claude_status_label.configure(
                    text="● Status: Inactive (Enter API key to activate)",
                    text_color=COLOR_TEXT_MUTED
                )
            self._add_feed_card("AI Brain", "Claude API key removed.", card_type="system")
        self._check_services()

    def _launch_ollama_service(self):
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._add_feed_card("System", "Initiating 'ollama serve' in background...", card_type="system")
            self.after(2000, self._check_services)
        except Exception as e:
            self._add_feed_card("System Error", f"Could not launch ollama: {e}", card_type="system")

    def _on_preset_selected(self, choice: str):
        self.brain_model_entry.delete(0, "end")
        self.brain_model_entry.insert(0, choice)
        self._apply_model_choice()

    def _apply_model_choice(self):
        model = self.brain_model_entry.get().strip()
        if model:
            config.AGENT_BRAIN_MODEL = model
            agent_brain.model = model
            self._add_feed_card("Settings", f"AI Brain model set to: {model}", card_type="system")
            self._check_services()

    def _test_brain_generation(self):
        prompt = self.test_prompt_entry.get().strip() or "open notepad and type hello"
        self._add_feed_card("AI Brain Test", f"Testing LLM code generation for: '{prompt}'", card_type="user")

        def worker():
            model = self.brain_model_entry.get().strip()
            agent_brain.model = model
            res = agent_brain.generate_and_execute(prompt)

            def update():
                self._add_feed_card(
                    f"Brain Result: {'Success' if res['success'] else 'Failed'}",
                    res.get("message", ""),
                    card_type="code",
                    code=agent_brain.last_code
                )
            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_voice_streamer(self):
        if not self.is_listening:
            self._start_voice_streamer()
        else:
            self._stop_voice_streamer()

    def _start_voice_streamer(self):
        try:
            from speech.streamer import SpeechStreamer, set_speech_streamer
            self.streamer = SpeechStreamer()
            set_speech_streamer(self.streamer)

            def on_text(text: str):
                self.after(0, lambda: self._add_feed_card("Transcribed Speech", text, card_type="user"))
                return self._execute_command_async(text)

            def on_wake():
                self.after(0, lambda: self._add_feed_card("Wake Word", "Listening for command...", card_type="system"))

            def on_energy(vol: float):
                meter_val = min(1.0, vol * 15.0)
                self.after(0, lambda: self.mic_level_bar.set(meter_val))

            self.streamer_thread = threading.Thread(
                target=self.streamer.start,
                kwargs={
                    "on_text_callback": on_text,
                    "on_wake_word_callback": on_wake,
                    "on_audio_energy_callback": on_energy
                },
                daemon=True
            )
            self.streamer_thread.start()
            self.is_listening = True
            self.streamer_btn.configure(text="⏹ Stop Voice", fg_color="#DC2626", hover_color="#991B1B")
            self.voice_status_label.configure(text="● Voice: Active", text_color=COLOR_ACCENT_GREEN)
            self._add_feed_card("Voice Streamer", "Voice recognition active. Say 'alexa' followed by your command.", card_type="system")
        except Exception as e:
            self._add_feed_card("Voice Error", f"Could not start speech streamer: {e}", card_type="system")

    def _stop_voice_streamer(self):
        if self.streamer:
            try:
                self.streamer.stop()
            except Exception:
                pass
        self.is_listening = False
        self.streamer_btn.configure(text="▶ Start Voice", fg_color=COLOR_ACCENT_GREEN, hover_color="#059669")
        self.voice_status_label.configure(text="● Voice: Idle", text_color="#F59E0B")
        self._add_feed_card("Voice Streamer", "Voice recognition stopped.", card_type="system")

    def _on_engine_changed(self, choice: str):
        if "whispercpp" in choice:
            config.SPEECH_ENGINE = "whispercpp"
            self.badge_engine.configure(text="🎙️ Engine: whispercpp")
        else:
            config.SPEECH_ENGINE = "faster_whisper"
            self.badge_engine.configure(text="🎙️ Engine: faster_whisper")

    def _save_groq_key(self):
        key = self.groq_key_entry.get().strip()
        config.GROQ_API_KEY = key
        os.environ["GROQ_API_KEY"] = key
        if key:
            self.groq_status_label.configure(
                text="● Status: Groq Cloud Whisper Active (~99% accuracy)",
                text_color=COLOR_ACCENT_GREEN
            )
            self.badge_engine.configure(text="🎙️ Engine: Groq Whisper (99%)")
            self._add_feed_card(
                "Voice Engine",
                "Groq Cloud Whisper Large-v3-Turbo activated! Voice commands will now be transcribed with ~99% accuracy in ~150ms.",
                card_type="system"
            )
        else:
            self.groq_status_label.configure(
                text="● Status: Inactive (Using Local CPU Whisper)",
                text_color=COLOR_TEXT_MUTED
            )
            engine = getattr(config, "SPEECH_ENGINE", "whispercpp")
            self.badge_engine.configure(text=f"🎙️ Engine: {engine}")
            self._add_feed_card("Voice Engine", "Groq API Key removed. Local CPU Whisper is active.", card_type="system")

    def _on_wake_changed(self, choice: str):
        config.WAKE_WORD_MODEL = choice
        self.badge_wake.configure(text=f"⚡ Wake: \"{choice}\"")
        if self.streamer:
            self.streamer.set_wake_word(choice)


def run_dashboard_app():
    """Main entrypoint for the CustomTkinter Dashboard."""
    app = Privacy68Dashboard()
    app.mainloop()


if __name__ == "__main__":
    run_dashboard_app()

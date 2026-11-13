"""
PRIVACY68 Push-to-Talk Floating Transparent Overlay
A compact, glassmorphic floating desktop widget that allows users to trigger
Click-to-Speak voice commands on-demand from the Windows System Tray or hotkey.
100% Zero-Idle microphone allocation: mic hardware opens ONLY during active speech.
"""

import logging
import threading
import time
from typing import Optional, Any
import tkinter as tk

logger = logging.getLogger("PRIVACY68.PTTOverlay")


class PushToTalkOverlay:
    """
    Compact, draggable, semi-transparent Push-to-Talk floating overlay.
    Triggered from the Windows System Tray menu: '🎙️ Voice Command (Push to Talk)'.
    """

    def __init__(self, parent_root: tk.Tk, ui_manager: Optional[Any] = None):
        self.parent_root = parent_root
        self.ui_manager = ui_manager
        self.window: Optional[tk.Toplevel] = None
        self.is_recording = False
        self.is_processing = False
        self.recorder = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._pulse_job = None
        self._pulse_state = False
        self._auto_stop_job = None

        self._build_window()

    def _build_window(self):
        """Constructs the glassmorphic frameless floating widget."""
        self.window = tk.Toplevel(self.parent_root)
        self.window.title("PRIVACY68 Push-to-Talk")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.attributes("-alpha", 0.94)
        except Exception:
            pass

        # Dimensions & screen positioning (bottom center, above taskbar)
        w, h = 390, 125
        sw = self.parent_root.winfo_screenwidth()
        sh = self.parent_root.winfo_screenheight()
        x = max(20, (sw - w) // 2)
        y = max(20, sh - h - 110)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.config(bg="#0c0e14")

        # Outer border frame
        outer = tk.Frame(self.window, bg="#1e2433", padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        self.main_container = tk.Frame(outer, bg="#0d111a", padx=12, pady=10)
        self.main_container.pack(fill="both", expand=True)

        # 1. Top Header Bar (Draggable + Title + Close Button)
        header = tk.Frame(self.main_container, bg="#0d111a")
        header.pack(fill="x", side="top", pady=(0, 6))

        # Drag handle & Title
        title_box = tk.Frame(header, bg="#0d111a")
        title_box.pack(side="left")

        dot = tk.Label(title_box, text="●", fg="#10b981", bg="#0d111a", font=("Segoe UI", 9, "bold"))
        dot.pack(side="left", padx=(0, 5))
        self.dot_label = dot

        title_lbl = tk.Label(
            title_box,
            text="PRIVACY68 // PUSH TO TALK",
            fg="#94a3b8",
            bg="#0d111a",
            font=("Segoe UI", 8, "bold")
        )
        title_lbl.pack(side="left")

        # Close button (✕)
        close_btn = tk.Label(
            header,
            text="✕",
            fg="#64748b",
            bg="#0d111a",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#f87171"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg="#64748b"))

        # Enable dragging from header and main background
        for w_item in (header, title_box, title_lbl, dot, self.main_container):
            w_item.bind("<Button-1>", self._on_drag_start)
            w_item.bind("<B1-Motion>", self._on_drag_motion)

        # 2. Middle Body: Mic Action Button (Left) + Status / Speech (Right)
        body = tk.Frame(self.main_container, bg="#0d111a")
        body.pack(fill="both", expand=True)

        # Large Microphone Click-to-Speak Button
        self.mic_btn = tk.Button(
            body,
            text="🎙️",
            font=("Segoe UI Emoji", 20),
            bg="#1e293b",
            fg="#f8fafc",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            width=3,
            height=1,
            cursor="hand2",
            command=self._on_mic_clicked
        )
        self.mic_btn.pack(side="left", padx=(0, 12))

        # Status & Transcribed Command Block
        info_frame = tk.Frame(body, bg="#0d111a")
        info_frame.pack(side="left", fill="both", expand=True)
        info_frame.bind("<Button-1>", self._on_drag_start)
        info_frame.bind("<B1-Motion>", self._on_drag_motion)

        self.status_title = tk.Label(
            info_frame,
            text="Click Mic to Speak",
            fg="#f8fafc",
            bg="#0d111a",
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        )
        self.status_title.pack(fill="x")

        self.status_subtitle = tk.Label(
            info_frame,
            text="Google Speech 1st • Offline Whisper Fallback",
            fg="#64748b",
            bg="#0d111a",
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=250,
            justify="left"
        )
        self.status_subtitle.pack(fill="x", pady=(2, 0))

        # Keyboard shortcut: Spacebar toggles speak when window is active
        self.window.bind("<space>", lambda e: self._on_mic_clicked())
        self.window.bind("<Escape>", lambda e: self.hide())

    def _on_drag_start(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        if self.window:
            x = self.window.winfo_x() + (event.x - self._drag_start_x)
            y = self.window.winfo_y() + (event.y - self._drag_start_y)
            self.window.geometry(f"+{x}+{y}")

    def is_alive(self) -> bool:
        """Returns True if the Tkinter window exists."""
        return self.window is not None and self.window.winfo_exists()

    def show(self):
        """Displays and focuses the overlay."""
        if not self.is_alive():
            self._build_window()
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)

    def hide(self):
        """Hides the overlay and cancels any active recording."""
        if self.is_recording:
            self._abort_recording()
        if self.is_alive():
            self.window.withdraw()

    def toggle(self):
        """Toggles between visible and hidden states."""
        if not self.is_alive():
            self.show()
        elif self.window.winfo_viewable():
            self.hide()
        else:
            self.show()

    def _on_mic_clicked(self):
        """Handles user clicking the microphone button."""
        if self.is_processing:
            return

        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_and_transcribe()

    def _start_recording(self):
        """Opens microphone hardware on-demand and begins capturing voice."""
        try:
            from speech.streamer import PushToTalkRecorder
            self.recorder = PushToTalkRecorder()
            self.recorder.start()
            self.is_recording = True

            # Visual state: Listening / Pulsing Red
            self.mic_btn.config(
                text="🔴",
                bg="#e11d48",
                activebackground="#be123c",
                fg="#ffffff"
            )
            self.dot_label.config(fg="#f43f5e")
            self.status_title.config(text="Listening...", fg="#fb7185")
            self.status_subtitle.config(text="Speak command, then click to send", fg="#94a3b8")

            # Start pulsing animation
            self._start_pulse()

            # Safety timeout: Auto-stop after 8 seconds if user forgets to click
            if self._auto_stop_job:
                self.window.after_cancel(self._auto_stop_job)
            self._auto_stop_job = self.window.after(8000, self._auto_stop_timer)

            if self.ui_manager and hasattr(self.ui_manager, "on_wake_word_detected"):
                self.ui_manager.on_wake_word_detected()

            logger.info("PTT Overlay: On-demand microphone recording started.")
        except Exception as e:
            logger.error(f"Failed to start PTT recording: {e}")
            self._set_state_ui("error", "Microphone Error", str(e))

    def _auto_stop_timer(self):
        """Auto-triggers stop when safety time limit is reached."""
        if self.is_recording:
            logger.info("PTT Overlay: Safety timer reached 8s; auto-stopping.")
            self._stop_and_transcribe()

    def _abort_recording(self):
        """Aborts recording without execution."""
        self._stop_pulse()
        if self._auto_stop_job and self.window:
            self.window.after_cancel(self._auto_stop_job)
            self._auto_stop_job = None
        if self.recorder:
            try:
                self.recorder.stop_and_transcribe()
            except Exception:
                pass
            self.recorder = None
        self.is_recording = False
        self.is_processing = False
        self._reset_to_idle()

    def _stop_and_transcribe(self):
        """Stops audio recording and dispatches transcription in a worker thread."""
        if not self.is_recording:
            return

        self.is_recording = False
        self.is_processing = True
        self._stop_pulse()
        if self._auto_stop_job and self.window:
            self.window.after_cancel(self._auto_stop_job)
            self._auto_stop_job = None

        # Visual state: Transcribing
        self.mic_btn.config(
            text="⚡",
            bg="#d97706",
            activebackground="#b45309",
            fg="#ffffff"
        )
        self.dot_label.config(fg="#f59e0b")
        self.status_title.config(text="Transcribing Voice...", fg="#fbbf24")
        self.status_subtitle.config(text="Processing with Google Speech...", fg="#94a3b8")

        # Run transcription & execution in background thread to keep UI buttery smooth
        threading.Thread(target=self._transcribe_and_execute_worker, daemon=True).start()

    def _transcribe_and_execute_worker(self):
        """Worker thread: transcribes audio, routes to command executor, and updates UI."""
        raw_text = ""
        try:
            if self.recorder:
                raw_text = self.recorder.stop_and_transcribe()
        except Exception as e:
            logger.error(f"PTT transcription exception: {e}")
        finally:
            self.recorder = None

        if not raw_text or not raw_text.strip():
            logger.info("PTT Overlay: No speech detected in audio capture.")
            self._schedule_ui(lambda: self._show_result("No Speech Detected", "Please speak closer to the mic and click again.", is_error=True))
            return

        command = raw_text.strip()
        logger.info(f"PTT Overlay Transcribed: '{command}'")

        # Notify UI Manager
        if self.ui_manager and hasattr(self.ui_manager, "on_transcription"):
            self.ui_manager.on_transcription(command)

        # Update overlay to show heard command
        self._schedule_ui(lambda: self._set_state_ui("processing", f'"{command}"', "Executing action..."))

        # Dispatch command execution
        msg = "Executed successfully."
        success = True
        try:
            from actions.executor import execute_system_command_detailed
            result = execute_system_command_detailed(
                command,
                on_action_callback=getattr(self.ui_manager, "on_action_completed", None),
                on_status_callback=getattr(self.ui_manager, "on_agent_status", None)
            )
            if isinstance(result, dict):
                success = result.get("success", True)
                msg = result.get("message") or ("Completed" if success else "Action failed")
        except Exception as exec_err:
            success = False
            msg = str(exec_err)

        final_title = f'"{command}"'
        final_msg = msg
        is_err = not success

        self._schedule_ui(lambda: self._show_result(final_title, final_msg, is_error=is_err))

    def _show_result(self, title: str, subtitle: str, is_error: bool = False):
        """Displays command outcome on the overlay, then auto-resets after 4s."""
        self.is_processing = False
        color = "#ef4444" if is_error else "#10b981"
        icon = "✖" if is_error else "✔"

        if self.is_alive():
            self.mic_btn.config(text=icon, bg=color, fg="#ffffff")
            self.dot_label.config(fg=color)
            self.status_title.config(text=title, fg=color)
            self.status_subtitle.config(text=subtitle, fg="#e2e8f0")

            # Auto-reset to ready state after 4 seconds
            self.window.after(4200, self._reset_to_idle)

    def _reset_to_idle(self):
        """Restores the overlay to the idle Click-to-Speak state."""
        if not self.is_alive() or self.is_recording or self.is_processing:
            return

        self.mic_btn.config(
            text="🎙️",
            bg="#1e293b",
            activebackground="#334155",
            fg="#f8fafc"
        )
        self.dot_label.config(fg="#10b981")
        self.status_title.config(text="Click Mic to Speak", fg="#f8fafc")
        self.status_subtitle.config(text="Google Speech 1st • Offline Whisper Fallback", fg="#64748b")

    def _set_state_ui(self, state: str, title: str, subtitle: str):
        """Updates UI elements safely."""
        if not self.is_alive():
            return
        if state == "processing":
            self.mic_btn.config(text="⚡", bg="#8b5cf6", fg="#ffffff")
            self.dot_label.config(fg="#8b5cf6")
            self.status_title.config(text=title, fg="#c084fc")
            self.status_subtitle.config(text=subtitle, fg="#94a3b8")
        elif state == "error":
            self._show_result(title, subtitle, is_error=True)

    def _schedule_ui(self, func):
        """Schedules a function to run on the Tkinter GUI thread."""
        if self.is_alive():
            try:
                self.window.after(0, func)
            except Exception:
                pass

    def _start_pulse(self):
        """Pulses the mic button while recording."""
        if not self.is_recording or not self.is_alive():
            return
        self._pulse_state = not self._pulse_state
        bg_col = "#f43f5e" if self._pulse_state else "#be123c"
        try:
            self.mic_btn.config(bg=bg_col)
            self._pulse_job = self.window.after(400, self._start_pulse)
        except Exception:
            pass

    def _stop_pulse(self):
        """Stops the pulsing animation."""
        if self._pulse_job and self.window:
            try:
                self.window.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None


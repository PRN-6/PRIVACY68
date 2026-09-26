import logging
import os
import sys
from typing import Optional
from ui.hud import FloatingHUD
from ui.tray import SystemTray

logger = logging.getLogger("PRIVACY68.UIManager")

class UIManager:
    """
    Central coordinator managing the Floating HUD and Windows System Tray.
    Thread-safe event bridge between audio pipeline, LLM actions, and UI visuals.
    """
    def __init__(self):
        self.hud = FloatingHUD()
        self.tray = SystemTray(ui_manager=self)
        self.is_muted = False
        self.streamer = None

    def set_streamer(self, streamer):
        """Connects the active SpeechStreamer instance."""
        self.streamer = streamer

    def start_tray(self):
        """Starts the tray in a background thread."""
        try:
            self.tray.start()
        except Exception as e:
            logger.warning(f"Could not start system tray: {e}")

    def run_hud_loop(self):
        """Runs the main HUD Tkinter loop on the main thread."""
        self.hud.start_ui()

    def on_wake_word_detected(self):
        """Triggered when the wake word is spotted."""
        if not self.is_muted:
            self.hud.set_state("listening", text="Listening for command...")
            self.tray.set_status_color("#EF4444")

    def on_audio_energy(self, level: float):
        """Updates live audio energy for waveform visualization."""
        if not self.is_muted:
            self.hud.update_audio_energy(level)

    def on_transcription(self, text: str):
        """Triggered when speech settles and transcription starts."""
        self.hud.set_state("processing", text=f'"{text}"')
        self.tray.set_status_color("#F97316")

    def on_agent_status(self, status_type: str, message: str):
        """Triggered during command execution status updates."""
        if not self.is_muted:
            if status_type in ("planning", "executing"):
                self.hud.set_state("agent", title="⚡ PRIVACY68", text=message)
                self.tray.set_status_color("#8B5CF6")
            elif status_type in ("completed", "success"):
                self.hud.set_state("success", title="✔ ACTION COMPLETED", text=message)
                self.tray.set_status_color("#10B981")
            elif status_type in ("error", "failed"):
                self.hud.set_state("error", title="✖ NOT RECOGNIZED", text=message)
                self.tray.set_status_color("#EF4444")

    def on_action_completed(self, tool_name: str, success: bool = True, message: Optional[str] = None):
        """Triggered when a skill finishes executing."""
        if success:
            display_title = f"⚡ {tool_name.replace('_', ' ').upper()}"
            display_text = message if message else "Executed successfully"
            self.hud.set_state("success", title=display_title, text=display_text)
            self.tray.set_status_color("#10B981")
        else:
            display_text = message if message else "Command not recognized"
            self.hud.set_state("error", text=display_text)
            self.tray.set_status_color("#EF4444")

    def on_sleep(self):
        """Triggered when speech times out or returns to idle."""
        if not self.is_muted:
            wake_name = (self.streamer.wake_word if self.streamer else "Privacy68").title()
            self.hud.set_state("idle", text=f"Say '{wake_name}' to begin")
            self.tray.set_status_color("#EF4444")

    def toggle_hud(self):
        """Toggles HUD visibility on/off."""
        self.hud.toggle_visibility()

    def open_mobile_remote(self):
        """Opens the Mobile Web Remote interface in the default browser."""
        import webbrowser
        import config
        from server.remote_server import get_remote_url
        url = get_remote_url(getattr(config, "REMOTE_SERVER_PORT", 8765))
        logger.info(f"Opening Mobile Web Remote in browser: {url}")
        webbrowser.open(url)

    def open_plugin_manager(self):
        """Opens the visual Plugin Manager window."""
        self.hud.open_plugin_manager()

    def toggle_mute(self):
        """Toggles assistant listening state."""
        self.is_muted = not self.is_muted
        if self.streamer:
            self.streamer.set_muted(self.is_muted)

        wake_name = (self.streamer.wake_word if self.streamer else "Privacy68").title()
        if self.is_muted:
            self.hud.set_state("error", title="🔇 PRIVACY68 MUTED", text="Microphone input paused")
            self.tray.set_status_color("#EF4444")
            logger.info("PRIVACY68 Muted (Microphone Paused).")
        else:
            self.hud.set_state("success", title="🎙️ PRIVACY68 ACTIVE", text=f"Listening for '{wake_name}'...")
            self.tray.set_status_color("#EF4444")
            logger.info("PRIVACY68 Unmuted (Microphone Listening).")

    def shutdown(self):
        """Gracefully shuts down HUD and application."""
        logger.info("Shutting down UI Manager...")
        self.hud.close()
        # Trigger process termination
        os._exit(0)

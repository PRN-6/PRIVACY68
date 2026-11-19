import tkinter as tk
import queue
import math
import ctypes
import logging

logger = logging.getLogger("PRIVACY68.HUD")

# Enable Windows DPI awareness for razor-sharp multi-monitor rendering
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception as e:
    logger.debug(f"SetProcessDpiAwareness unavailable: {e}")
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:
        logger.debug(f"SetProcessDPIAware unavailable: {e}")


class FloatingHUD:
    """
    A cinematic, full-screen transparent HUD overlay for PRIVACY68.
    Features:
    - 100% click-through (WS_EX_TRANSPARENT) so games & apps are completely unobstructed.
    - Multi-tiered high-intensity glowing neon laser border around monitor edges on speech detection.
    - Sci-Fi corner reticles, top telemetry badge, and animated equalizer audio waveform.
    - Zero text/artifacts when idle: Screen is 100% clear.
    - Dynamic bottom-center glassmorphic speech & transcription pill when user speaks.
    """
    def __init__(self, on_close_callback=None):
        self.on_close_callback = on_close_callback
        self.queue = queue.Queue()
        self.root = None
        self.canvas = None
        self.current_state = "idle"
        self.visible = True
        
        # Canvas Background Transparency
        self.transparent_color = "#010101"
        self.text_primary = "#FFFFFF"
        self.text_secondary = "#E2E8F0"
        self.pill_bg = "#0A0A0E"
        
        # Color Palettes per State: (Accent Line, Soft Bloom, Subtle Halo)
        self.themes = {
            "idle": {
                "accent": "#010101", "bloom": "#010101", "halo": "#010101",
                "badge": "IDLE"
            },
            "listening": {
                "accent": "#F43F5E", "bloom": "#E11D48", "halo": "#881337",
                "badge": "● PRIVACY68 // LISTENING"
            },
            "processing": {
                "accent": "#FB7185", "bloom": "#BE123C", "halo": "#4C0519",
                "badge": "⚡ PRIVACY68 // PROCESSING"
            },
            "success": {
                "accent": "#10B981", "bloom": "#059669", "halo": "#064E3B",
                "badge": "✔ PRIVACY68 // ACTION EXECUTED"
            },
            "error": {
                "accent": "#EF4444", "bloom": "#B91C1C", "halo": "#7F1D1D",
                "badge": "✖ PRIVACY68 // UNKNOWN COMMAND"
            },
            "agent": {
                "accent": "#A78BFA", "bloom": "#8B5CF6", "halo": "#5B21B6",
                "badge": "⚡ PRIVACY68 // ASSISTANT"
            }
        }
        
        # Animation & telemetry
        self.pulse_phase = 0.0
        self.audio_level = 0.0
        
        # Subtitle text
        self.status_title = ""
        self.status_subtitle = ""
        self.status_icon = ""
        
        # Dimensions
        self.sw = 1920
        self.sh = 1080

    def start_ui(self):
        """Initializes the background Tkinter context without displaying any screen border overlay."""
        self.root = tk.Tk()
        self.root.title("PRIVACY68 Background Service")
        self.root.withdraw()  # Completely hidden - no screen border or monitor overlay!

        # Start event polling
        self._poll_events()

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.close()

    def _enable_click_through(self):
        pass

    def _draw_rounded_rect(self, *args, **kwargs):
        pass

    def _draw_hud(self):
        """No-op: screen borders and HUD drawing completely removed."""
        pass

    def _animate_pulse(self):
        pass

    def _poll_events(self):
        """Polls thread-safe messages from background audio and executor threads."""
        try:
            while True:
                action, data = self.queue.get_nowait()
                if action == "state":
                    self._set_state_internal(data)
                elif action == "energy":
                    self.audio_level = data
                elif action == "text":
                    self.status_subtitle = data
                    self._draw_hud()
                elif action == "toggle_visibility":
                    self._toggle_visibility_internal()
                elif action == "open_plugins":
                    self._open_plugins_internal()
                elif action == "show_ptt_overlay":
                    self._show_ptt_overlay_internal(data)
                elif action == "quit":
                    if self.root:
                        try:
                            self.root.quit()
                            self.root.destroy()
                        except Exception as e:
                            logger.debug(f"_poll_events: {e}")
                        self.root = None
                    return
        except queue.Empty:
            pass
            
        try:
            if self.root:
                self.root.after(25, self._poll_events)
        except Exception as e:
            logger.debug(f"_poll_events: {e}")

    def _open_plugins_internal(self):
        from ui.plugin_window import PluginManagerWindow
        if not hasattr(self, "_plugin_win") or self._plugin_win is None:
            self._plugin_win = PluginManagerWindow(parent_root=self.root)
        self._plugin_win.open()

    def _set_state_internal(self, state_data):
        """Applies state changes within the GUI thread."""
        state = state_data.get("name", "idle")
        self.current_state = state
        
        if state == "idle":
            self.status_icon = ""
            self.status_title = ""
            self.status_subtitle = ""
            self.audio_level = 0.0
            
        elif state == "listening":
            self.status_icon = "🎙️"
            self.status_title = "LISTENING"
            self.status_subtitle = state_data.get("text", "Listening for your command...")
            
        elif state == "processing":
            self.status_icon = "⚡"
            self.status_title = "PROCESSING"
            self.status_subtitle = state_data.get("text", "Thinking...")
            
        elif state == "success":
            self.status_icon = "🚀"
            self.status_title = state_data.get("title", "ACTION EXECUTED")
            self.status_subtitle = state_data.get("text", "Completed successfully")
            try:
                if self.root:
                    self.root.after(2800, lambda: self._set_state_internal({"name": "idle"}))
            except Exception as e:
                logger.debug(f"_set_state_internal: {e}")
                
        elif state == "error":
            self.status_icon = "⚠️"
            self.status_title = "UNKNOWN COMMAND"
            self.status_subtitle = state_data.get("text", "Command not recognized")
            try:
                if self.root:
                    self.root.after(2800, lambda: self._set_state_internal({"name": "idle"}))
            except Exception as e:
                logger.debug(f"_set_state_internal: {e}")
                
        self._draw_hud()

    def _toggle_visibility_internal(self):
        if not self.root:
            return
        if self.visible:
            self.root.withdraw()
            self.visible = False
        else:
            self.root.deiconify()
            self.visible = True

    # ---------------- Thread-Safe Public API ---------------- #

    def set_state(self, name: str, text: str = None, title: str = None):
        """Thread-safe state update."""
        payload = {"name": name}
        if text:
            payload["text"] = text
        if title:
            payload["title"] = title
        self.queue.put(("state", payload))

    def update_audio_energy(self, level: float):
        """Thread-safe audio energy update for waveform visualization."""
        self.queue.put(("energy", level))

    def set_subtitle_text(self, text: str):
        """Thread-safe subtitle/transcript update."""
        self.queue.put(("text", text))

    def toggle_visibility(self):
        """Thread-safe toggle HUD visibility."""
        self.queue.put(("toggle_visibility", None))

    def open_plugin_manager(self):
        """Thread-safe open Plugin Manager Window."""
        self.queue.put(("open_plugins", None))

    def show_ptt_overlay(self, ui_manager=None):
        """Thread-safe request to show or toggle the Push-to-Talk floating overlay."""
        self.queue.put(("show_ptt_overlay", ui_manager))

    def _show_ptt_overlay_internal(self, ui_manager=None):
        try:
            from ui.ptt_overlay import PushToTalkOverlay
            if not hasattr(self, "_ptt_overlay") or self._ptt_overlay is None or not self._ptt_overlay.is_alive():
                self._ptt_overlay = PushToTalkOverlay(parent_root=self.root, ui_manager=ui_manager)
                self._ptt_overlay.show()
            else:
                self._ptt_overlay.toggle()
        except Exception as e:
            logger.error(f"Error displaying PTT overlay: {e}")

    def close(self):
        """Thread-safe window shutdown."""
        self.queue.put(("quit", None))

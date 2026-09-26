import tkinter as tk
import queue
import threading
import time
import math
import ctypes

# Enable Windows DPI awareness for razor-sharp multi-monitor rendering
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


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
        """Initializes the Tkinter window and starts its main loop."""
        self.root = tk.Tk()
        self.root.title("PRIVACY68 Fullscreen HUD Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Desktop screen dimensions
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.root.geometry(f"{self.sw}x{self.sh}+0+0")
        
        # Transparency setup
        self.root.config(bg=self.transparent_color)
        try:
            self.root.wm_attributes("-transparentcolor", self.transparent_color)
        except Exception:
            pass
        
        # Full-screen canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.sw,
            height=self.sh,
            bg=self.transparent_color,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Bind Escape key to cleanly close the overlay if focused
        self.root.bind("<Escape>", lambda e: self.close())
        
        # Enable full click-through (mouse clicks pass through to background apps)
        self._enable_click_through()
        
        # Start redraw & animation loops
        self._draw_hud()
        self._poll_events()
        self._animate_pulse()
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.close()

    def _enable_click_through(self):
        """Enables WS_EX_TRANSPARENT and WS_EX_NOACTIVATE so mouse clicks pass through the overlay."""
        try:
            # Force Tkinter to map the window so the parent HWND exists
            self.root.update_idletasks()
            self.root.update()
            
            hwnd_child = self.root.winfo_id()
            hwnd_parent = ctypes.windll.user32.GetParent(hwnd_child) or hwnd_child
            
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            LWA_COLORKEY = 0x00000001
            
            # 64-bit safe Get/SetWindowLong
            SetWindowLong = getattr(ctypes.windll.user32, 'SetWindowLongPtrW', ctypes.windll.user32.SetWindowLongW)
            GetWindowLong = getattr(ctypes.windll.user32, 'GetWindowLongPtrW', ctypes.windll.user32.GetWindowLongW)
            SetWindowLong.restype = ctypes.c_longlong
            SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
            GetWindowLong.restype = ctypes.c_longlong
            GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
            
            # CRITICAL: Extended layered styles must ONLY be applied to the top-level parent window, NEVER child widgets
            style = GetWindowLong(hwnd_parent, GWL_EXSTYLE)
            SetWindowLong(hwnd_parent, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            
            # Re-apply color key transparency so Windows DWM treats #010101 as 100% transparent
            col_hex = self.transparent_color.lstrip('#')
            col_int = int(col_hex, 16)
            r = (col_int >> 16) & 0xFF
            g = (col_int >> 8) & 0xFF
            b = col_int & 0xFF
            colorref = r | (g << 8) | (b << 16)
            
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd_parent, colorref, 0, LWA_COLORKEY)
        except Exception:
            pass

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Draws a smooth rounded pill rectangle on the canvas."""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw_hud(self):
        """Redraws the entire full-screen glowing overlay based on current state."""
        self.canvas.delete("all")
        
        # If in idle state, do not draw text or heavy borders — screen is 100% clean
        if self.current_state == "idle":
            return
            
        sw = self.sw
        sh = self.sh
        theme = self.themes.get(self.current_state, self.themes["listening"])
        
        # Dynamic pulse calculation
        pulse = (math.sin(self.pulse_phase) + 1.0) / 2.0  # 0.0 to 1.0
        
        # ─────────────────────────────────────────────────────────────
        # 1. SUBTLE GLOWING BORDER (Inside screen margin)
        # ─────────────────────────────────────────────────────────────
        margin = 12
        
        # Layer 1: Ambient Halo Depth (Subtle & soft)
        halo_w = int(3 + pulse * 2)
        self.canvas.create_rectangle(
            margin, margin, sw - margin, sh - margin,
            outline=theme["halo"],
            width=halo_w
        )
        
        # Layer 2: Slim Crisp Accent Border
        self.canvas.create_rectangle(
            margin, margin, sw - margin, sh - margin,
            outline=theme["accent"],
            width=1
        )
        
        # ─────────────────────────────────────────────────────────────
        # 2. MINIMALIST CORNER RETICLES
        # ─────────────────────────────────────────────────────────────
        blen = 32
        bthick = 2
        accent_col = theme["accent"]
        
        # Top-Left Bracket
        self.canvas.create_line(margin - 1, margin, margin + blen, margin, fill=accent_col, width=bthick)
        self.canvas.create_line(margin, margin - 1, margin, margin + blen, fill=accent_col, width=bthick)
        
        # Top-Right Bracket
        self.canvas.create_line(sw - margin - blen, margin, sw - margin + 1, margin, fill=accent_col, width=bthick)
        self.canvas.create_line(sw - margin, margin - 1, sw - margin, margin + blen, fill=accent_col, width=bthick)
        
        # Bottom-Left Bracket
        self.canvas.create_line(margin - 1, sh - margin, margin + blen, sh - margin, fill=accent_col, width=bthick)
        self.canvas.create_line(margin, sh - margin - blen, margin, sh - margin + 1, fill=accent_col, width=bthick)
        
        # Bottom-Right Bracket
        self.canvas.create_line(sw - margin - blen, sh - margin, sw - margin + 1, sh - margin, fill=accent_col, width=bthick)
        self.canvas.create_line(sw - margin, sh - margin - blen, sw - margin, sh - margin + 1, fill=accent_col, width=bthick)
        
        # ─────────────────────────────────────────────────────────────
        # 3. TOP TELEMETRY RIBBON BADGE
        # ─────────────────────────────────────────────────────────────
        badge_text = theme.get("badge", "PRIVACY68")
        top_cx = sw // 2
        top_cy = margin + 16
        
        # Glass pill for top badge
        self._draw_rounded_rect(
            top_cx - 120, top_cy - 11,
            top_cx + 120, top_cy + 11,
            radius=8,
            fill="#0C0C10",
            outline=theme["accent"],
            width=1.2
        )
        self.canvas.create_text(
            top_cx, top_cy,
            text=badge_text,
            fill=theme["accent"],
            font=("Segoe UI", 9, "bold")
        )
        
        # ─────────────────────────────────────────────────────────────
        # 4. DYNAMIC BOTTOM-CENTER SPEECH PILL
        # ─────────────────────────────────────────────────────────────
        if self.status_subtitle or self.status_title:
            text_to_show = self.status_subtitle or self.status_title
            pill_width = min(720, max(420, len(text_to_show) * 11 + 150))
            pill_height = 64
            
            # Position at bottom-center (85px above bottom bezel)
            pill_x1 = (sw - pill_width) // 2
            pill_y1 = sh - pill_height - 80
            pill_x2 = pill_x1 + pill_width
            pill_y2 = pill_y1 + pill_height
            
            # Outer Bloom Halo for Pill
            self._draw_rounded_rect(
                pill_x1 - 2, pill_y1 - 2, pill_x2 + 2, pill_y2 + 2,
                radius=22,
                fill=self.transparent_color,
                outline=theme["bloom"],
                width=3
            )
            
            # Main Glassmorphic Pill
            self._draw_rounded_rect(
                pill_x1, pill_y1, pill_x2, pill_y2,
                radius=20,
                fill=self.pill_bg,
                outline=theme["accent"],
                width=1.5
            )
            
            # Icon Orb (Left)
            icon_cx = pill_x1 + 34
            icon_cy = pill_y1 + (pill_height // 2)
            
            self.canvas.create_oval(
                icon_cx - 15, icon_cy - 15,
                icon_cx + 15, icon_cy + 15,
                fill="#111827",
                outline=theme["accent"],
                width=1.5
            )
            self.canvas.create_text(
                icon_cx, icon_cy,
                text=self.status_icon,
                font=("Segoe UI Emoji", 11)
            )
            
            # Status Text Labels
            text_x = pill_x1 + 60
            
            if self.status_title and self.status_subtitle:
                # 2-line layout
                self.canvas.create_text(
                    text_x, icon_cy - 9,
                    anchor="w",
                    text=self.status_title,
                    fill=theme["accent"],
                    font=("Segoe UI", 9, "bold")
                )
                
                # Subtitle (clean truncation if very long)
                sub = self.status_subtitle
                if len(sub) > 60:
                    sub = sub[:57] + "..."
                self.canvas.create_text(
                    text_x, icon_cy + 10,
                    anchor="w",
                    text=sub,
                    fill=self.text_primary,
                    font=("Segoe UI", 10)
                )
            else:
                # Single bold line
                self.canvas.create_text(
                    text_x, icon_cy,
                    anchor="w",
                    text=text_to_show,
                    fill=self.text_primary,
                    font=("Segoe UI", 10, "bold")
                )
            
            # Equalizer Audio Waveform Bars (Right side)
            if self.current_state in ("listening", "processing"):
                bar_count = 6
                bar_gap = 6
                bar_start_x = pill_x2 - (bar_count * bar_gap) - 20
                for i in range(bar_count):
                    # Combine audio energy with sine phase for animated equalizer
                    bar_pulse = math.sin(self.pulse_phase * 2.0 + i * 0.8)
                    base_amp = max(4, int(self.audio_level * 140))
                    amp = int(base_amp * (0.6 + 0.4 * bar_pulse)) if self.current_state == "listening" else int(7 + 5 * bar_pulse)
                    amp = min(24, max(4, amp))
                    
                    self.canvas.create_line(
                        bar_start_x + (i * bar_gap), icon_cy - amp // 2,
                        bar_start_x + (i * bar_gap), icon_cy + amp // 2,
                        fill=theme["accent"],
                        width=2.5,
                        capstyle=tk.ROUND
                    )

    def _animate_pulse(self):
        """Smooth micro-animation loop for border glow and waveform."""
        if not self.root:
            return
            
        try:
            if self.current_state in ("listening", "processing"):
                self.pulse_phase += 0.14
                self._draw_hud()
            elif self.current_state in ("success", "error"):
                self.pulse_phase += 0.08
                self._draw_hud()
                
            self.root.after(30, self._animate_pulse)
        except Exception:
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
                elif action == "quit":
                    if self.root:
                        try:
                            self.root.quit()
                            self.root.destroy()
                        except Exception:
                            pass
                        self.root = None
                    return
        except queue.Empty:
            pass
            
        try:
            if self.root:
                self.root.after(25, self._poll_events)
        except Exception:
            pass

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
            except Exception:
                pass
                
        elif state == "error":
            self.status_icon = "⚠️"
            self.status_title = "UNKNOWN COMMAND"
            self.status_subtitle = state_data.get("text", "Command not recognized")
            try:
                if self.root:
                    self.root.after(2800, lambda: self._set_state_internal({"name": "idle"}))
            except Exception:
                pass
                
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

    def close(self):
        """Thread-safe window shutdown."""
        self.queue.put(("quit", None))

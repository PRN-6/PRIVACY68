import threading
import logging
from PIL import Image, ImageDraw
import pystray
import webbrowser

logger = logging.getLogger("PRIVACY68.SystemTray")

class SystemTray:
    """
    Windows System Tray integration for PRIVACY68 Assistant.
    Updated to the Agentic Architecture: provides status tracking and brain controls.
    """
    def __init__(self, ui_manager):
        self.ui_manager = ui_manager
        self.icon = None
        self.is_running = False
        self.current_status = "Online"

    def _create_icon_image(self, color="#EF4444"):
        """Generates a dynamic 64x64 icon with a glowing rounded circle."""
        width = 64
        height = 64
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Outer ring
        draw.ellipse((4, 4, 60, 60), fill="#111115", outline=color, width=4)
        # Inner core
        draw.ellipse((20, 20, 44, 44), fill=color)

        return image

    def start(self):
        """Starts the tray icon in a dedicated background thread."""
        image = self._create_icon_image("#EF4444")

        # Build the Agentic Menu
        menu = pystray.Menu(
            pystray.MenuItem(f"🤖 Status: {self.current_status}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📊 Open Dashboard", self._on_open_dashboard),
            pystray.MenuItem("📱 Open Mobile Remote", self._on_open_mobile_remote),
            pystray.MenuItem("🧹 Reset Brain Session", self._on_reset_brain),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🚪 Exit PRIVACY68", self._on_exit)
        )

        self.icon = pystray.Icon(
            "PRIVACY68",
            image,
            "PRIVACY68 Agentic Core",
            menu=menu
        )

        self.is_running = True
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()
        logger.info("Agentic System Tray icon initialized.")

    def _on_open_dashboard(self):
        """Opens the Control Center Dashboard via the UI Manager."""
        if self.ui_manager:
            self.ui_manager.open_dashboard()
        else:
            logger.error("UI Manager not found; cannot open dashboard.")

    def _on_open_mobile_remote(self):
        """Opens the local web remote using the dynamic project URL."""
        try:
            from server.remote_server import get_remote_url
            # Get the correct IP and port (default 8765)
            url = get_remote_url()
            webbrowser.open(url)
            logger.info(f"Opening mobile remote at: {url}")
        except Exception as e:
            logger.error(f"Could not open remote: {e}")

    def _on_open_settings(self):
        # In the new lean architecture, settings are handled in the Web UI
        self._on_open_mobile_remote()

    def _on_reset_brain(self):
        """Tells the AgentBrain to clear its session state."""
        logger.info("Resetting Agent Brain session via tray.")
        if self.ui_manager:
            # If your ui_manager has a reset method, call it here
            if hasattr(self.ui_manager, 'reset_agent'):
                self.ui_manager.reset_agent()

    def _on_exit(self):
        logger.info("Exit requested via System Tray.")
        if self.icon:
            self.icon.stop()
        if self.ui_manager:
            self.ui_manager.shutdown()

    def update_status(self, status: str, color: str = "#EF4444"):
        """Updates the tray icon color and the status menu text."""
        self.current_status = status
        if self.icon and self.is_running:
            try:
                # Update icon color
                self.icon.icon = self._create_icon_image(color)
            except Exception as e:
                logger.debug(f"Could not update tray icon: {e}")

    def set_status_color(self, color_hex: str):
        """Compatibility method to update the tray icon color."""
        self.update_status("Online", color_hex)

import threading
import logging
from PIL import Image, ImageDraw
import pystray

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
            pystray.MenuItem("⌨️ Run Command (Quick Command Bar)", self._on_command, default=True),
            pystray.MenuItem("📊 Open Dashboard", self._on_open_dashboard),
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

    def _on_command(self):
        """Show or hide the text command bar."""
        if self.ui_manager:
            self.ui_manager.show_command_bar()

    def _on_open_dashboard(self):
        """Opens the Control Center Dashboard via the UI Manager."""
        if self.ui_manager:
            self.ui_manager.open_dashboard()
        else:
            logger.error("UI Manager not found; cannot open dashboard.")

    def _on_exit(self):
        logger.info("Exit requested via System Tray.")
        if self.ui_manager:
            self.ui_manager.shutdown()

    def stop(self):
        if self.icon:
            self.icon.stop()
        self.is_running = False

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

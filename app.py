import os
import sys
import logging
import threading

# ─────────────────────────────────────────────────────────────────────────────
# 1. PyInstaller frozen-safe base directory resolution
#    sys._MEIPASS is set when running as a compiled .exe — use it as base.
#    Falls back to the script's own directory when running from source.
# ─────────────────────────────────────────────────────────────────────────────
IS_FROZEN = getattr(sys, "frozen", False)
BASE_DIR = sys._MEIPASS if IS_FROZEN else os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# 2. User AppData Directory — safe persistent storage for logs & config
# ─────────────────────────────────────────────────────────────────────────────
APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "PRIVACY68")
os.makedirs(APPDATA_DIR, exist_ok=True)
LOG_FILE = os.path.join(APPDATA_DIR, "privacy68.log")

logger = logging.getLogger("PRIVACY68.Core")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Logging — always write to AppData log file; only echo to stdout if a
#    console is attached (i.e. not in --windowed EXE mode where stdout=None).
# ─────────────────────────────────────────────────────────────────────────────
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"module: {e}")

if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"module: {e}")

log_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger("PRIVACY68.Core")

logger.info(f"PRIVACY68 starting — frozen={IS_FROZEN}, base={BASE_DIR}")
logger.info(f"Log file: {LOG_FILE}")

import config


def main() -> None:
    if "--run-agent-script" in sys.argv:
        from actions.agent_runner import execute_agent_script

        arguments = sys.argv[1:]
        if len(arguments) != 3 or arguments[0] != "--run-agent-script":
            logger.error("Invalid internal Agent Brain runner arguments.")
            raise SystemExit(2)
        raise SystemExit(execute_agent_script(arguments[1], arguments[2]))

    if "--dashboard" in sys.argv or "--settings" in sys.argv:
        logger.info("Launching PRIVACY68 Control Center Dashboard...")
        try:
            from ui.dashboard_runner import run_dashboard
            run_dashboard()
        except Exception:
            logger.exception("The PRIVACY68 Control Center failed to start.")
            raise SystemExit(1)
        return

    from actions.executor import execute_system_command, execute_system_command_detailed
    from ui.manager import UIManager

    logger.info("Initializing PRIVACY68 Assistant Services...")

    ui_manager = UIManager()

    try:
        # Start System Tray in background
        ui_manager.start_tray()

        # Auto-start Telegram Remote Gateway if configured and enabled
        try:
            from channels.telegram import telegram_channel
            if getattr(config, "ENABLE_TELEGRAM_BOT", True) and telegram_channel.get_bot_token():
                ok, msg = telegram_channel.start_bot()
                if ok:
                    logger.info(f"✈️ {msg}")
                else:
                    logger.debug(f"Telegram Bot start note: {msg}")
        except Exception as tg_err:
            logger.debug(f"Could not initialize Telegram Bot on startup: {tg_err}")

        # Run the Floating HUD Tkinter loop on the main thread
        logger.info("Starting PRIVACY68 Background Service...")
        ui_manager.run_hud_loop()

    except KeyboardInterrupt:
        logger.info("Graceful shutdown sequence initialized by user.")
    except Exception as e:
        logger.critical(f"Unhandled fatal error in main thread: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Cleanup completed. PRIVACY68 is offline.")


if __name__ == "__main__":
    main()
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

# CUDA registration is optional and must happen after logging is ready: in the
# windowed executable, an exception here otherwise prevents every app mode
# from starting and leaves no diagnostic log.
try:
    from utils.cuda_manager import register_cuda_dlls
    register_cuda_dlls()
except Exception:
    logger.exception("Could not register optional CUDA runtime DLL paths; continuing without CUDA setup.")

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

    from speech.streamer import SpeechStreamer, set_speech_streamer
    from actions.executor import execute_system_command, execute_system_command_detailed
    from ui.manager import UIManager
    from server.remote_server import start_remote_server, stop_remote_server

    logger.info("Initializing PRIVACY68 Assistant Services...")

    ui_manager = UIManager()

    def on_text_transcribed(text: str) -> bool:
        """Callback hook executed whenever a transcription segment settles."""
        logger.info(f"User: '{text}'")
        if sys.stdout is not None:
            try:
                sys.stdout.write(f"\r[User Input] {text}\n")
                sys.stdout.flush()
            except Exception as e:
                logger.debug(f"on_text_transcribed: {e}")

        ui_manager.on_transcription(text)
        return execute_system_command(
            text,
            on_action_callback=ui_manager.on_action_completed,
            on_status_callback=ui_manager.on_agent_status
        )

    def on_remote_command(text: str) -> dict:
        """Callback hook executed when a command is dispatched from the Mobile Web Remote."""
        logger.info(f"Mobile Remote Command: '{text}'")
        if sys.stdout is not None:
            try:
                sys.stdout.write(f"\r[Mobile Remote] {text}\n")
                sys.stdout.flush()
            except Exception as e:
                logger.debug(f"on_remote_command: {e}")

        ui_manager.on_transcription(text)
        result = execute_system_command_detailed(
            text,
            on_action_callback=ui_manager.on_action_completed,
            on_status_callback=ui_manager.on_agent_status
        )
        return result

    try:
        # Start System Tray in background
        ui_manager.start_tray()

        # Start Mobile Web Remote Server in background
        if getattr(config, "ENABLE_REMOTE_SERVER", True):
            remote_url = start_remote_server(
                on_command_callback=on_remote_command,
                host=getattr(config, "REMOTE_SERVER_HOST", "0.0.0.0"),
                port=getattr(config, "REMOTE_SERVER_PORT", 8765)
            )
            logger.info(f"📱 Mobile Web Remote listening at: {remote_url}")

        # Initialize Audio Streamer and register module-level singleton
        streamer = SpeechStreamer()
        set_speech_streamer(streamer)
        ui_manager.set_streamer(streamer)

        # Run speech streamer in a dedicated worker thread
        audio_thread = threading.Thread(
            target=streamer.start,
            kwargs={
                "on_text_callback": on_text_transcribed,
                "on_wake_word_callback": ui_manager.on_wake_word_detected,
                "on_audio_energy_callback": ui_manager.on_audio_energy,
                "on_sleep_callback": ui_manager.on_sleep
            },
            daemon=True
        )
        audio_thread.start()

        # Run the Floating HUD Tkinter loop on the main thread
        logger.info("Starting PRIVACY68 Floating HUD Overlay...")
        ui_manager.run_hud_loop()

    except KeyboardInterrupt:
        logger.info("Graceful shutdown sequence initialized by user.")
    except Exception as e:
        logger.critical(f"Unhandled fatal error in main thread: {e}", exc_info=True)
        sys.exit(1)
    finally:
        stop_remote_server()
        logger.info("Cleanup completed. PRIVACY68 is offline.")


if __name__ == "__main__":
    main()
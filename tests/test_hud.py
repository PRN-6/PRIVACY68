import time
import threading
import math
import sys
from ui.hud import FloatingHUD

# Ensure Windows terminal handles UTF-8 safely without UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_simulated_waveform(hud, duration=3.0):
    """Simulates live microphone audio energy levels."""
    start = time.time()
    phase = 0.0
    while time.time() - start < duration:
        level = (math.sin(phase) + 1.0) / 2.0 * 0.7 + 0.15
        hud.update_audio_energy(level)
        phase += 0.4
        time.sleep(0.04)

def run_automated_showcase(hud):
    """Runs the full visual showcase demo across all states."""
    try:
        print("\n▶ [1/4] State: LISTENING (Cyan border + dynamic audio bars)", flush=True)
        hud.set_state("listening", text="Listening for your command...")
        run_simulated_waveform(hud, duration=2.5)

        print("▶ [2/4] State: PROCESSING (Violet border + transcription)", flush=True)
        hud.set_state("processing", text='"open google chrome and search quantum computing"')
        time.sleep(2.0)

        print("▶ [3/4] State: SUCCESS (Emerald border + action banner)", flush=True)
        hud.set_state("success", title="⚡ GOOGLE CHROME", text="Tab launched successfully")
        time.sleep(2.0)

        print("▶ [4/4] State: ERROR (Crimson border + warning)", flush=True)
        hud.set_state("error", text="Command not recognized by LLM router")
        time.sleep(2.0)

        print("▶ State: IDLE (Screen is 100% clean and transparent)\n", flush=True)
        hud.set_state("idle")
    except Exception as e:
        print(f"Error during showcase: {e}", flush=True)

def interactive_demo(hud):
    try:
        _run_interactive_loop(hud)
    except Exception as e:
        print(f"\nTester error: {e}", flush=True)
    finally:
        hud.close()

def _run_interactive_loop(hud):
    print("\n" + "=" * 55, flush=True)
    print(" 🚀 PRIVACY68 HUD Overlay — Interactive Visual Tester", flush=True)
    print(" 💡 The overlay is 100% click-through (apps & clicks work normally).", flush=True)
    print("=" * 55, flush=True)
    print(" 🎮 Options:", flush=True)
    print("   [a] - Run Automated Showcase Demo", flush=True)
    print("   [1] - Test 'Listening' (with audio waveform)", flush=True)
    print("   [2] - Test 'Processing' (with custom text)", flush=True)
    print("   [3] - Test 'Success'", flush=True)
    print("   [4] - Test 'Error'", flush=True)
    print("   [5] - Reset to 'Idle' (Screen clean)", flush=True)
    print("   [q] - Quit tester (or press Ctrl+C)", flush=True)
    print("=" * 55 + "\n", flush=True)

    while True:
        try:
            cmd = input("Select an option (a, 1-5, q): ").strip().lower()
            if cmd == "a":
                threading.Thread(target=run_automated_showcase, args=(hud,), daemon=True).start()
            elif cmd == "1":
                hud.set_state("listening", text="Say your command now...")
                threading.Thread(target=run_simulated_waveform, args=(hud, 3.5), daemon=True).start()
            elif cmd == "2":
                text = input("  Enter transcription text (or press Enter for default): ").strip()
                if not text:
                    text = "turn the volume up to maximum"
                hud.set_state("processing", text=f'"{text}"')
            elif cmd == "3":
                title = input("  Enter action title (or press Enter for default): ").strip()
                if not title:
                    title = "⚡ SYSTEM VOLUME"
                hud.set_state("success", title=title, text="Executed successfully")
            elif cmd == "4":
                hud.set_state("error", text="Could not process speech request")
            elif cmd == "5":
                hud.set_state("idle")
                print("  HUD set to Idle (Transparent).", flush=True)
            elif cmd in ("q", "quit", "exit"):
                print("Closing HUD overlay...", flush=True)
                hud.close()
                break
        except (KeyboardInterrupt, EOFError):
            print("\nExiting tester...", flush=True)
            hud.close()
            break

def main():
    hud = FloatingHUD()
    
    # Run the interactive demo in a background controller thread
    tester_thread = threading.Thread(target=interactive_demo, args=(hud,), daemon=True)
    tester_thread.start()

    # The Tkinter GUI main loop must run on the main thread
    try:
        hud.start_ui()
    except (KeyboardInterrupt, SystemExit):
        hud.close()
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()

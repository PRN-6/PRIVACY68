"""
    Hand Gesture Control Plugin for PRIVACY68 Assistant
    ====================================================
    Uses the webcam (MediaPipe Hands + OpenCV) to recognize hand gestures in
    real time and control the assistant and system:

        ✋ Open Palm  (5 fingers)   -> Wake assistant / begin listening
        ✊ Fist       (0 fingers)   -> Toggle microphone mute
        👍 Thumb-only pointed L/R -> PPT: prev/next slide  |  other windows: prev/next desktop
        ☝️ 1 finger               -> PPT: previous slide
        ✌️ 2 fingers              -> PPT: next slide  (scratch/scroll outside PPT)
        🤟 3 fingers               -> Volume down
        🖐️ 4 fingers               -> Volume up
        👋 Palm swipe left/right   -> Previous / next slide (Left/Right keys)

    ALT-TAB app switcher mode (voice: "open app switcher"):
        ✋ Palm  (held)             -> Hold Alt (overlay stays open)
        ✊ Fist  (repeat)           -> Cycle to the next app (Tab)
        👌 Index+thumb (pinch)     -> Select & open the highlighted app

    Dependencies:  pip install mediapipe opencv-python pyautogui
    The plugin loads gracefully even if these packages are missing; gesture
    actions simply report failure with an install hint.
"""

import logging
import math
import threading
import time
from typing import Callable, Dict, List

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("PRIVACY68.Plugin.Gesture")

# ─────────────────────────────────────────────────────────────────────────────
# Optional dependency loading — plugin stays loadable without them
# ─────────────────────────────────────────────────────────────────────────────
try:
    import cv2
    import numpy as np
    import pyautogui
    import mediapipe as mp
    try:
        import mediapipe.solutions.hands as mp_hands_mod
        import mediapipe.solutions.drawing_utils as mp_draw_mod
        _mp_hands = mp_hands_mod
        _mp_draw = mp_draw_mod
    except (ImportError, AttributeError):
        # mediapipe >= 0.10.x moved solutions under mediapipe.python.solutions
        import mediapipe.python.solutions.hands as mp_hands_mod
        import mediapipe.python.solutions.drawing_utils as mp_draw_mod
        _mp_hands = mp_hands_mod
        _mp_draw = mp_draw_mod
    _HAS_DEPS = True
except Exception as e:  # pragma: no cover
    cv2 = np = pyautogui = mp = None
    _mp_hands = _mp_draw = None
    _HAS_DEPS = False
    _DEPS_ERROR = e
    logger.warning(f"Gesture plugin dependencies missing ({e}). "
                   "Install with: pip install mediapipe opencv-python pyautogui")

# ─────────────────────────────────────────────────────────────────────────────
# Gesture tuning knobs
# ─────────────────────────────────────────────────────────────────────────────
GESTURE_CONFIG = {
    "camera_id": 0,
    "max_fps": 15.0,                 # cap inference loop to save CPU
    "show_preview": True,            # small debug window showing hand overlay
    "wake_hold_frames": 8,           # palm must be held this many frames to wake
    "wake_cooldown": 3.0,            # seconds between palm-wake triggers
    "mute_hold_frames": 8,           # fist holds to mute
    "mute_cooldown": 1.5,            # seconds between mute toggles
    "volume_hold_frames": 6,         # 3/4 finger holds to change volume
    "volume_repeat": 0.4,            # repeat interval while keeping pose
    "swipe_distance": 0.18,          # normalized horizontal palm travel
    "swipe_window": 0.35,            # seconds allowed for a swipe
    "swipe_cooldown": 1.0,
    "pinch_distance": 0.06,          # normalized thumb<->index distance for click

    # Thumbs-up left/right: slides in PPT, desktop switch otherwise
    "thumb_hold_frames": 6,          # thumb pose frames to trigger
    "thumb_cooldown": 1.2,           # seconds between triggers
    "thumb_direction_threshold": 0.10,  # normalized dx (tip vs MCP) for left/right

    # PPT finger navigation: 1 finger = prev slide, 2 fingers = next slide
    "ppt_finger_hold_frames": 5,     # hold to trigger (prevents flaky detections)
    "ppt_finger_repeat": 0.5,        # seconds between repeats while held

    # Alt-Tab app switcher mode
    "alt_tab_hold_frames": 4,        # palm frames to press & hold Alt
    "alt_tab_repeat": 0.35,          # seconds between fist->Tab cycles while held
    "alt_tab_cooldown": 1.5,         # seconds between Alt-Tab mode activations
    "alt_tab_sequence_window": 0.8,  # palm-(within)-fist opens Alt-Tab hands-free
}

if _HAS_DEPS and _mp_hands is None:
    try:
        _mp_hands = mp.solutions.hands
        _mp_draw = mp.solutions.drawing_utils
    except AttributeError:
        pass



def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fingers_up(landmarks: dict) -> List[bool]:
    """Returns [thumb, index, middle, ring, pinky] raised flags.

    `landmarks` maps MediaPipe landmark index -> (x, y, z) normalized coords.
    Thumb uses distance-to-wrist heuristic; fingers use tip-vs-pip height.
    """
    lm = landmarks
    d_tip = _dist(lm[4], lm[0])
    d_ip = _dist(lm[3], lm[0])
    thumb = d_tip > d_ip * 1.1
    index = lm[8][1] < lm[6][1]
    middle = lm[12][1] < lm[10][1]
    ring = lm[16][1] < lm[14][1]
    pinky = lm[20][1] < lm[18][1]
    return [thumb, index, middle, ring, pinky]


class HandGestureEngine:
    """Runs the webcam gesture detection loop in a dedicated thread."""

    def __init__(self, on_action):
        self.on_action = on_action
        self._stop = threading.Event()
        self._thread = None
        self._cap = None
        self._alt_tab_enabled = False

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> bool:
        if not _HAS_DEPS:
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="GestureEngine")
        self._thread.start()
        logger.info("Gesture engine started.")
        return True

    def stop(self) -> None:
        self._stop.set()
        self.release_alt()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Gesture engine stopped.")

    @property
    def alt_tab_enabled(self) -> bool:
        return self._alt_tab_enabled

    def set_alt_tab_mode(self, enabled: bool) -> bool:
        self._alt_tab_enabled = enabled
        if not enabled:
            self.release_alt()
        logger.info(f"Alt-Tab mode {'ENABLED' if enabled else 'DISABLED'}.")
        return enabled

    def release_alt(self) -> None:
        """Ensures the Alt key (held for the app switcher) is released."""
        try:
            pyautogui.keyUp("alt")
        except Exception:
            pass

    def toggle_preview(self) -> bool:
        GESTURE_CONFIG["show_preview"] = not GESTURE_CONFIG["show_preview"]
        return GESTURE_CONFIG["show_preview"]

    # ── main loop ─────────────────────────────────────────────────────────
    def _run(self):
        try:
            cap = cv2.VideoCapture(GESTURE_CONFIG["camera_id"])
            if not cap.isOpened():
                logger.error("Gesture engine: webcam could not be opened.")
                return
            self._cap = cap

            with _mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            ) as hands:
                self._loop(cap, hands)
        except Exception as e:
            logger.error(f"Gesture engine crashed: {e}", exc_info=True)
        finally:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def _loop(self, cap, hands):
        cfg = GESTURE_CONFIG
        frame_interval = 1.0 / cfg["max_fps"]

        # hold / cooldown state
        wake_frames = mute_frames = vol_frames = thumb_frames = 0
        last_wake = last_mute = last_vol = last_swipe = last_thumb = 0.0
        vol_dir = 0

        # alt-tab state
        alt_active = False
        alt_frames = 0
        last_alt_tab = 0.0
        last_alt_trigger = 0.0
        last_tab = 0.0

        # palm->fist sequence detection (hands-free Alt-Tab entry)
        seq_palm_time = 0.0

        # palm trajectory for swipe detection
        palm_trace = []           # (timestamp, normalized_x)

        # scroll state
        pinch_down = False
        scroll_accum = 0.0
        last_index_y = None

        # PPT 1-finger / 2-finger slide navigation state
        ppt_frames = 0
        last_ppt = 0.0
        ppt_dir = 0

        while not self._stop.is_set():
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = hands.process(rgb)
            rgb.flags.writeable = True

            now = time.time()
            raw_lm = None

            if results.multi_hand_landmarks:
                hl = results.multi_hand_landmarks[0]
                raw_lm = {
                    i: (hl.landmark[i].x, hl.landmark[i].y, hl.landmark[i].z)
                    for i in range(21)
                }
                if cfg["show_preview"]:
                    _mp_draw.draw_landmarks(frame, hl, _mp_hands.HAND_CONNECTIONS)

            if raw_lm is not None:
                f_up = fingers_up(raw_lm)
                count = sum(f_up)
                palm_x, palm_y = raw_lm[9][0], raw_lm[9][1]

                # ── Palm swipe detection (prev/next slide) ──────────────
                if f_up[1] and f_up[2] and f_up[3] and f_up[4] and not f_up[0]:
                    palm_trace.append((now, palm_x))
                    palm_trace = [(ts, x) for ts, x in palm_trace if now - ts <= cfg["swipe_window"]]
                    if now - last_swipe > cfg["swipe_cooldown"] and len(palm_trace) >= 3:
                        x0 = palm_trace[0][1]
                        dx = palm_x - x0
                        if abs(dx) >= cfg["swipe_distance"]:
                            direction = "right" if dx > 0 else "left"
                            logger.info(f"Gesture: Palm swipe {direction}")
                            pyautogui.press("right" if direction == "left" else "left")
                            self._feedback()
                            last_swipe = now
                            palm_trace = []
                else:
                    palm_trace = []

                # ── Static pose classification ───────────────────────────
                if self._alt_tab_enabled:
                    # ── ALT-TAB mode: palm=hold Alt, fist=cycle, pinch=select ──
                    if count == 5 and f_up[0]:          # open palm -> HOLD Alt
                        seq_palm_time = now
                        if not alt_active and now - last_alt_trigger > cfg["alt_tab_cooldown"]:
                            alt_frames += 1
                            if alt_frames >= cfg["alt_tab_hold_frames"]:
                                alt_active = True
                                last_tab = now - cfg["alt_tab_repeat"]
                        else:
                            alt_frames = 0
                        if alt_active:
                            pyautogui.keyDown("alt")
                    elif count == 0:                    # fist -> CYCLE (send Tab)
                        alt_frames = 0
                        if alt_active and now - last_tab > cfg["alt_tab_repeat"]:
                            last_tab = now
                            logger.info("Gesture: Alt+Tab — next app")
                            pyautogui.keyDown("alt")
                            pyautogui.press("tab")
                            self._feedback()
                    # pointing (index only, below) is checked AFTER this block,
                    # and pinch there SELECTS while alt_active.
                    else:
                        alt_frames = 0

                    wake_frames = mute_frames = vol_frames = thumb_frames = vol_dir = 0
                elif count == 5 and f_up[0]:  # full open palm -> wake
                    seq_palm_time = now
                    wake_frames += 1
                    mute_frames = vol_frames = vol_dir = 0
                    if wake_frames >= cfg["wake_hold_frames"] and now - last_wake > cfg["wake_cooldown"]:
                        last_wake = now
                        wake_frames = 0
                        logger.info("Gesture: Open palm — waking assistant")
                        self._wake_assistant()
                        self._feedback()
                elif count == 0:           # fist -> mute toggle (or alt-tab entry)
                    # hands-free Alt-Tab: if a full palm was shown moments ago,
                    # interpret this fist as "cycle the app switcher".
                    if now - seq_palm_time <= cfg["alt_tab_sequence_window"] and not self._alt_tab_enabled:
                        self._alt_tab_enabled = True
                        logger.info("Gesture: Palm → Fist — Alt-Tab mode ON")
                        alt_active = True
                        last_tab = now - cfg["alt_tab_repeat"]
                        seq_palm_time = 0.0
                    else:
                        wake_frames = vol_frames = vol_dir = 0
                        mute_frames += 1
                        if mute_frames >= cfg["mute_hold_frames"] and now - last_mute > cfg["mute_cooldown"]:
                            last_mute = now
                            mute_frames = 0
                            logger.info("Gesture: Fist — toggling microphone")
                            self._toggle_mute()
                            self._feedback()
                elif count == 1 and f_up[0]:  # thumbs-up -> left/right navigation
                    wake_frames = mute_frames = vol_frames = thumb_frames = vol_dir = 0
                    thumb_dx = raw_lm[4][0] - raw_lm[2][0]   # tip vs MCP (mirrored: left=user right)
                    thumb_frames += 1
                    if thumb_frames >= cfg["thumb_hold_frames"] and now - last_thumb > cfg["thumb_cooldown"]:
                        if abs(thumb_dx) >= cfg["thumb_direction_threshold"]:
                            last_thumb = now
                            thumb_frames = 0
                            direction = "right" if thumb_dx < 0 else "left"   # thumb tip side = user intent
                            if _foreground_is_powerpoint():
                                logger.info(f"Gesture: Thumb {direction} — PPT slide")
                                pyautogui.press("right" if direction == "right" else "left")
                            else:
                                logger.info(f"Gesture: Thumb {direction} — desktop switch")
                                pyautogui.hotkey("win", "ctrl", "right" if direction == "right" else "left")
                            self._feedback()
                elif count == 1 and f_up[1]:  # index only -> PPT: previous slide
                    wake_frames = mute_frames = thumb_frames = vol_frames = vol_dir = 0
                    ppt_dir = -1
                    ppt_frames += 1
                    if _foreground_is_powerpoint() and ppt_frames >= cfg["ppt_finger_hold_frames"]:
                        if now - last_ppt > cfg["ppt_finger_repeat"]:
                            last_ppt = now
                            logger.info("Gesture: 1 finger — previous slide")
                            pyautogui.press("left")
                            self._feedback()
                elif count == 2 and f_up[1] and f_up[2]:  # 2 fingers -> PPT: next slide
                    wake_frames = mute_frames = thumb_frames = vol_frames = vol_dir = 0
                    ppt_dir = 1
                    ppt_frames += 1
                    if _foreground_is_powerpoint() and ppt_frames >= cfg["ppt_finger_hold_frames"]:
                        if now - last_ppt > cfg["ppt_finger_repeat"]:
                            last_ppt = now
                            logger.info("Gesture: 2 fingers — next slide")
                            pyautogui.press("right")
                            self._feedback()
                elif count == 3 or count == 4:  # volume control (thumb relaxed)
                    wake_frames = mute_frames = 0
                    vol_dir = -1 if count == 3 else 1
                    vol_frames += 1
                    if vol_frames >= cfg["volume_hold_frames"]:
                        if now - last_vol > cfg["volume_repeat"]:
                            last_vol = now
                            if vol_dir > 0:
                                logger.info("Gesture: 4 fingers — volume up")
                                pyautogui.press("volumeup")
                            else:
                                logger.info("Gesture: 3 fingers — volume down")
                                pyautogui.press("volumedown")
                else:
                    wake_frames = mute_frames = vol_frames = thumb_frames = ppt_frames = vol_dir = 0

                # ── Index+thumb pinch -> Alt-Tab select (any finger count) ─
                if self._alt_tab_enabled:
                    ix, iy = raw_lm[8][0], raw_lm[8][1]
                    tx, ty = raw_lm[4][0], raw_lm[4][1]
                    pinching = _dist((ix, iy), (tx, ty)) < cfg["pinch_distance"]
                    if pinching and not pinch_down:
                        logger.info("Gesture: Pinch — select app")
                        pyautogui.press("enter")
                        self._feedback()
                        pinch_down = True
                    elif not pinching and pinch_down:
                        pinch_down = False

                # ── Peace sign (index+middle) -> scroll ─────────────────
                if f_up[1] and f_up[2] and not f_up[3] and not f_up[4] and not _foreground_is_powerpoint():
                    mid_y = (raw_lm[8][1] + raw_lm[12][1]) / 2.0
                    if last_index_y is None:
                        scroll_accum = 0.0
                    else:
                        scroll_accum += (last_index_y - mid_y) * 1200.0
                        steps = int(scroll_accum)
                        if steps != 0:
                            pyautogui.scroll(steps)
                            scroll_accum -= steps
                    last_index_y = mid_y
                else:
                    last_index_y = None
                    scroll_accum = 0.0

            else:
                wake_frames = mute_frames = vol_frames = thumb_frames = ppt_frames = vol_dir = 0
                palm_trace = []
                if pinch_down:
                    pinch_down = False
                last_index_y = None
                if alt_active:
                    self.release_alt()
                    alt_active = False
                seq_palm_time = 0.0

            if cfg["show_preview"] and _HAS_DEPS:
                label = _gesture_label()
                if raw_lm is not None:
                    label = _classify_text(raw_lm, self._alt_tab_enabled)
                cv2.putText(frame, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                cv2.imshow("PRIVACY68 Gesture Control", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self._stop.set()
                    break

            elapsed = time.time() - t0
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    # ── action hooks ─────────────────────────────────────────────────────
    def _wake_assistant(self):
        try:
            from speech.streamer import speech_streamer
            if speech_streamer is not None:
                speech_streamer.is_active = True
                if hasattr(speech_streamer, "vad"):
                    speech_streamer.vad.reset()
                logger.info("Gesture: Assistant is now listening for a command.")
        except Exception as e:
            logger.warning(f"Gesture: Could not wake assistant: {e}")

    def _toggle_mute(self):
        try:
            from speech.streamer import speech_streamer
            if speech_streamer is not None and hasattr(speech_streamer, "toggle_mute"):
                speech_streamer.toggle_mute()
                return
        except Exception:
            pass
        pyautogui.press("volumemute")

    @staticmethod
    def _feedback():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass


def _foreground_is_powerpoint() -> bool:
    """True if the active window belongs to PowerPoint (incl. slide show)."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = (buf.value or "").lower()
        return "powerpoint" in title
    except Exception:
        return False


def _gesture_label() -> str:
    return "PRIVACY68 Gesture Control"


def _classify_text(landmarks: dict, alt_tab: bool = False) -> str:
    f_up = fingers_up(landmarks)
    count = sum(f_up)
    if alt_tab:
        if count == 5 and f_up[0]:
            return "Alt-Tab: Hold Alt (keep palm)"
        if count == 0:
            return "Alt-Tab: Cycle (fist)"
        if count == 1 and f_up[1]:
            return "Alt-Tab: Select (pinch)"
        return "Alt-Tab active"
    if count == 5 and f_up[0]:
        return "Open Palm: Wake"
    if count == 0:
        return "Fist: Mute"
    if count == 1 and f_up[0]:
        return "Thumb: Left/Right Nav"
    if count == 1 and f_up[1]:
        return "1 Finger: Prev Slide"
    if count == 2 and f_up[1] and f_up[2]:
        return "2 Fingers: Next Slide"
    if count == 3:
        return "3 Fingers: Volume Down"
    if count == 4:
        return "4 Fingers: Volume Up"
    return "Detecting..."


class GesturePlugin(BasePlugin):
    id = "gesture"
    name = "Hand Gestures"
    icon = "✋"
    description = "Control PRIVACY68 and your PC with webcam hand gestures."
    version = "1.1.0"
    author = "Community Plugin"
    is_builtin = False

    def __init__(self, is_enabled: bool = True):
        super().__init__(is_enabled)
        self.engine = HandGestureEngine(on_action=None)

    @property
    def actions(self) -> Dict[str, Callable[[str], bool]]:
        return {
            "gesture.enable": self.enable_gestures,
            "gesture.disable": self.disable_gestures,
            "gesture.toggle_preview": self.toggle_preview,
            "gesture.alt_tab": self.open_alt_tab,
            "gesture.close_alt_tab": self.close_alt_tab,
        }

    @property
    def fast_intents(self) -> Dict[str, List[str]]:
        return {
            "gesture.enable": [
                "enable hand gestures",
                "enable hand gesture",
                "enable gesture control",
                "enable gestures",
                "enable gesture",
                "enable and gestures",
                "start hand gestures",
                "start hand gesture",
                "start gesture control",
                "turn on hand gestures",
                "turn on hand gesture",
                "turn on gesture control",
                "turn gestures on",
                "gestures on",
                "gesture mode on",
                "enable webcam gestures",
                "start webcam gestures",
                "activate hand gestures",
            ],
            "gesture.disable": [
                "disable hand gestures",
                "disable hand gesture",
                "disable gesture control",
                "disable gestures",
                "disable gesture",
                "stop hand gestures",
                "stop hand gesture",
                "stop gesture control",
                "turn off hand gestures",
                "turn off hand gesture",
                "turn off gesture control",
                "turn gestures off",
                "gestures off",
                "gesture mode off",
                "disable webcam gestures",
                "stop webcam gestures",
                "deactivate hand gestures",
            ],
            "gesture.toggle_preview": [
                "toggle gesture preview",
                "show gesture preview",
                "hide gesture preview",
                "toggle camera preview",
            ],
            "gesture.alt_tab": [
                "open app switcher",
                "open alt tab",
                "start app switcher",
                "enable alt tab mode",
                "alt tab mode",
                "show open windows",
                "show open apps",
                "open the app switcher",
                "enable app switcher",
            ],
            "gesture.close_alt_tab": [
                "close app switcher",
                "close alt tab",
                "stop app switcher",
                "stop alt tab",
                "disable app switcher",
                "disable alt tab mode",
                "quit app switcher",
                "exit app switcher",
            ],
        }

    @property
    def descriptions(self) -> Dict[str, str]:
        return {
            "gesture.enable": "- gesture.enable: Turn on webcam hand gesture control for the assistant.",
            "gesture.disable": "- gesture.disable: Turn off webcam hand gesture control.",
            "gesture.toggle_preview": "- gesture.toggle_preview: Show or hide the hand gesture camera overlay window.",
            "gesture.alt_tab": "- gesture.alt_tab: Enter Alt-Tab app switcher mode. Open palm holds Alt, fist cycles apps, index+thumb pinch selects.",
            "gesture.close_alt_tab": "- gesture.close_alt_tab: Leave Alt-Tab app switcher mode.",
        }

    def enable_gestures(self, text: str = "") -> bool:
        if not _HAS_DEPS:
            logger.error("Gesture plugin missing dependencies. "
                         "Install with: pip install mediapipe opencv-python pyautogui")
            return False
        if not self.engine.start():
            logger.error("Gesture engine failed to start (camera unavailable?).")
            return False
        logger.info("Hand gesture control ENABLED.")
        return True

    def disable_gestures(self, text: str = "") -> bool:
        self.engine.stop()
        logger.info("Hand gesture control DISABLED.")
        return True

    def toggle_preview(self, text: str = "") -> bool:
        state = self.engine.toggle_preview()
        logger.info(f"Gesture preview {'shown' if state else 'hidden'}.")
        return state

    def open_alt_tab(self, text: str = "") -> bool:
        if not _HAS_DEPS:
            logger.error("Gesture plugin missing dependencies.")
            return False
        if not self.engine._thread or not self.engine._thread.is_alive():
            if not self.engine.start():
                logger.error("Gesture engine failed to start (camera unavailable?).")
                return False
        self.engine.set_alt_tab_mode(True)
        return True

    def close_alt_tab(self, text: str = "") -> bool:
        self.engine.set_alt_tab_mode(False)
        return True
import os
import sys
import json
import logging
import platform
import shutil
import subprocess
from typing import Dict, Any, List
import sounddevice as sd
import numpy as np

from plugins.manager import plugin_manager
from plugins.profile_manager import profile_manager
from speech.voice_auth import voice_authenticator

logger = logging.getLogger("PRIVACY68.DashboardBridge")

class DashboardAPI:
    """
    Python-to-JavaScript IPC Bridge.
    All public methods in this class are accessible inside the WebView window
    via `window.pywebview.api.<method_name>()`.
    """
    def __init__(self, window=None):
        self._window = window

    def set_window(self, window):
        self._window = window

    # ---------------- Profile & Settings ---------------- #

    def get_profile(self) -> Dict[str, Any]:
        """Returns the full user profile & settings dictionary."""
        try:
            return {
                "user_name": profile_manager.get("user_name", "User"),
                "assistant_name": profile_manager.get("assistant_name", "Privacy68"),
                "wake_word": profile_manager.get("wake_word", "privacy68"),
                "wake_threshold": float(profile_manager.get("wake_threshold", 0.50)),
                "whisper_model": profile_manager.get("whisper_model", "small.en"),
                "hud_enabled": bool(profile_manager.get("hud_enabled", True)),
                "theme": profile_manager.get("theme", "obsidian_red"),
                "voice_lock_enabled": bool(profile_manager.get("voice_lock_enabled", False)),
                "voice_lock_threshold": float(profile_manager.get("voice_lock_threshold", 0.70)),
            }
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return {}

    def save_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves updated settings to user_profile.json."""
        try:
            profile_manager.update_multiple(data)
            logger.info("Saved user profile via Dashboard API.")
            return {"success": True, "message": "Preferences saved successfully!"}
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            return {"success": False, "message": str(e)}


    # ---------------- Plugin Management ---------------- #

    def get_plugins(self) -> List[Dict[str, Any]]:
        """Returns a list of all installed plugins with metadata."""
        try:
            plugins = plugin_manager.get_all_plugins()
            result = []
            for p in plugins:
                # Gather voice trigger phrases
                triggers = []
                for phrases in p.fast_intents.values():
                    if phrases:
                        triggers.extend(phrases[:2])

                result.append({
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "icon": p.icon,
                    "is_enabled": bool(p.is_enabled),
                    "is_builtin": getattr(p, "is_builtin", False),
                    "triggers": triggers[:5]
                })
            return result
        except Exception as e:
            logger.error(f"Error getting plugins: {e}")
            return []

    def toggle_plugin(self, plugin_id: str, enabled: bool) -> Dict[str, Any]:
        """Enables or disables a specific plugin."""
        try:
            plugin_manager.set_plugin_enabled(plugin_id, enabled)
            return {"success": True, "plugin_id": plugin_id, "enabled": enabled}
        except Exception as e:
            logger.error(f"Error toggling plugin {plugin_id}: {e}")
            return {"success": False, "message": str(e)}

    def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstalls and deletes a custom user plugin."""
        try:
            success = plugin_manager.uninstall_plugin(plugin_id)
            if success:
                return {"success": True, "message": f"Plugin '{plugin_id}' uninstalled."}
            else:
                return {"success": False, "message": "Cannot uninstall built-in core plugins."}
        except Exception as e:
            logger.error(f"Error uninstalling plugin: {e}")
            return {"success": False, "message": str(e)}

    def create_plugin(self, data: Dict[str, str]) -> Dict[str, Any]:
        """Generates a new plugin from template."""
        try:
            pid = data.get("id", "").strip().lower().replace(" ", "_")
            pname = data.get("name", "").strip()
            picon = data.get("icon", "🔌").strip() or "🔌"
            pdesc = data.get("desc", f"Controls {pname} application").strip()
            pcmd = data.get("cmd", f"open {pname}").strip()

            if not pid or not pname:
                return {"success": False, "message": "Plugin ID and Name are required."}

            file_created = plugin_manager.create_plugin_template(pid, pname, picon, pdesc, pcmd)
            return {
                "success": True,
                "message": f"Plugin '{pname}' created and activated!",
                "filename": os.path.basename(file_created)
            }
        except Exception as e:
            logger.error(f"Error creating plugin: {e}")
            return {"success": False, "message": str(e)}

    def pick_plugin_file(self) -> str:
        """Opens native file picker to select a .py or .zip plugin."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                title="Select PRIVACY68 Plugin File",
                filetypes=[("PRIVACY68 Plugin Files", "*.py *.zip"), ("Python Files", "*.py"), ("All Files", "*.*")]
            )
            root.destroy()
            return file_path or ""
        except Exception as e:
            logger.error(f"Error opening file dialog: {e}")
            return ""

    def install_plugin_file(self, file_path: str) -> Dict[str, Any]:
        """Installs a plugin from selected file path."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "message": "Invalid file path selected."}

            success = plugin_manager.install_plugin_from_file(file_path)
            if success:
                return {"success": True, "message": f"Plugin installed successfully: {os.path.basename(file_path)}"}
            else:
                return {"success": False, "message": "Could not install plugin file."}
        except Exception as e:
            logger.error(f"Error installing plugin file: {e}")
            return {"success": False, "message": str(e)}

    # ---------------- WhatsApp Contacts ---------------- #

    def get_whatsapp_contacts(self) -> List[Dict]:
        """Returns the saved WhatsApp contacts list for the plugin config UI."""
        try:
            from plugins.manager import plugin_manager
            plugin = plugin_manager.get_plugin("whatsapp")
            if plugin and hasattr(plugin, "load_contacts"):
                return plugin.load_contacts()
        except Exception as e:
            logger.error(f"Error loading WhatsApp contacts: {e}")
        return []

    def save_whatsapp_contacts(self, contacts: List[Dict]) -> Dict:
        """Saves the WhatsApp contacts list from the plugin config UI."""
        try:
            from plugins.manager import plugin_manager
            plugin = plugin_manager.get_plugin("whatsapp")
            if plugin and hasattr(plugin, "save_contacts"):
                success = plugin.save_contacts(contacts)
                return {"success": success, "message": f"Saved {len(contacts)} contacts." if success else "Save failed."}
            return {"success": False, "message": "WhatsApp plugin not found or not loaded."}
        except Exception as e:
            logger.error(f"Error saving WhatsApp contacts: {e}")
            return {"success": False, "message": str(e)}

    # ---------------- System Diagnostics & Telemetry ---------------- #


    def get_system_diagnostics(self) -> List[Dict[str, Any]]:
        """Runs hardware and environment health checks."""
        sections = []

        # 1. AI & Speech Engines
        ai_checks = []
        
        # Ollama Server
        ollama_path = shutil.which("ollama")
        if ollama_path:
            try:
                r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=4)
                models = [l.split()[0] for l in r.stdout.strip().split("\n")[1:] if l.strip()]
                if models:
                    ai_checks.append({
                        "name": "Ollama Server",
                        "status": "ok",
                        "detail": f"Installed & Running • {len(models)} model(s) available ({', '.join(models[:2])})",
                        "link": None
                    })
                else:
                    ai_checks.append({
                        "name": "Ollama Server",
                        "status": "warn",
                        "detail": "Running, but no models found. Run: ollama pull qwen2.5:0.5b",
                        "link": None
                    })
            except Exception:
                ai_checks.append({
                    "name": "Ollama Server",
                    "status": "warn",
                    "detail": "Installed but not responding. Start Ollama from your system tray.",
                    "link": None
                })
        else:
            ai_checks.append({
                "name": "Ollama Server",
                "status": "fail",
                "detail": "Ollama not found. Required for local AI reasoning and skills.",
                "link": "https://ollama.com/download"
            })

        # faster-whisper
        try:
            import faster_whisper
            ai_checks.append({
                "name": "faster-whisper (ASR)",
                "status": "ok",
                "detail": f"Loaded v{getattr(faster_whisper, '__version__', '1.0+')} • High-speed Whisper Engine",
                "link": None
            })
        except ImportError:
            ai_checks.append({
                "name": "faster-whisper (ASR)",
                "status": "fail",
                "detail": "Not installed in environment.",
                "link": None
            })

        sections.append({"title": "Core AI & Speech Engines", "icon": "cpu", "items": ai_checks})

        # 2. NVIDIA GPU & CUDA Acceleration
        gpu_checks = []
        try:
            from utils.cuda_manager import get_cuda_status
            cuda_stat = get_cuda_status()
            
            if cuda_stat["has_gpu"]:
                gpu_checks.append({
                    "name": "NVIDIA GPU",
                    "status": "ok",
                    "detail": f"{cuda_stat['gpu_name']} • {cuda_stat['free_memory']} free / {cuda_stat['total_memory']} • Driver {cuda_stat['driver_version']}",
                    "link": None
                })

                if cuda_stat["has_cuda_dlls"]:
                    gpu_checks.append({
                        "name": "CUDA 12 Runtime",
                        "status": "ok",
                        "detail": f"GPU Acceleration Active • {cuda_stat['dll_count']} CUDA libraries loaded",
                        "link": None,
                        "can_download": False
                    })
                else:
                    gpu_checks.append({
                        "name": "CUDA 12 Runtime",
                        "status": "warn",
                        "detail": "CUDA runtime libraries not installed. Speech engine is running in CPU mode.",
                        "link": cuda_stat["download_url"],
                        "can_download": True,
                        "action": "download_cuda",
                        "action_label": "Download CUDA (~450MB)"
                    })
            else:
                gpu_checks.append({
                    "name": "Hardware Compute Engine",
                    "status": "ok",
                    "detail": "Running on Multi-core CPU (Quantized INT8). Fast and zero setup required.",
                    "link": None
                })
        except Exception as e:
            gpu_checks.append({
                "name": "Hardware Compute Engine",
                "status": "ok",
                "detail": f"Default CPU mode active: {e}",
                "link": None
            })

        sections.append({"title": "Hardware Acceleration & Compute", "icon": "zap", "items": gpu_checks})

        # 3. Audio & Hardware Input
        hw_checks = []
        try:
            devices = sd.query_devices()
            input_devs = [d for d in devices if d['max_input_channels'] > 0]
            if input_devs:
                default_in = sd.query_devices(kind='input')
                hw_checks.append({
                    "name": "Microphone Hardware",
                    "status": "ok",
                    "detail": f"{len(input_devs)} input device(s) • Default: {default_in['name'][:35]}",
                    "link": None
                })
            else:
                hw_checks.append({
                    "name": "Microphone Hardware",
                    "status": "fail",
                    "detail": "No audio recording devices found! Please connect a microphone.",
                    "link": None
                })
        except Exception as e:
            hw_checks.append({
                "name": "Microphone Hardware",
                "status": "fail",
                "detail": f"Audio subsystem error: {e}",
                "link": None
            })

        hw_checks.append({
            "name": "Operating System",
            "status": "ok",
            "detail": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
            "link": None
        })

        sections.append({"title": "Audio Input & System Specs", "icon": "mic", "items": hw_checks})

        return sections

    def test_microphone(self) -> Dict[str, Any]:
        """Records a 0.4s audio slice to measure current mic volume/energy."""
        try:
            duration = 0.4
            sr = 16000
            recording = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")
            sd.wait()
            rms = float(np.sqrt(np.mean(recording**2)))
            level_pct = min(100, int(rms * 500))
            return {"success": True, "level": level_pct, "rms": rms}
        except Exception as e:
            return {"success": False, "level": 0, "message": str(e)}

    # ---------------- Voice Lock (Speaker Verification) ---------------- #

    def get_voice_lock_status(self) -> Dict[str, Any]:
        """Returns the current state of Voice Lock biometrics."""
        try:
            status = voice_authenticator.get_status()
            status["enabled"] = bool(profile_manager.get("voice_lock_enabled", False))
            status["threshold"] = float(profile_manager.get("voice_lock_threshold", 0.50))
            return status
        except Exception as e:
            logger.error(f"Error getting voice lock status: {e}")
            return {"enabled": False, "is_enrolled": False, "threshold": 0.50, "error": str(e)}

    def toggle_voice_lock(self, enabled: bool) -> Dict[str, Any]:
        """Enables or disables Voice Lock gating."""
        try:
            profile_manager.set("voice_lock_enabled", enabled)
            logger.info(f"Voice Lock set to {'ENABLED' if enabled else 'DISABLED'}")
            return {"success": True, "enabled": enabled}
        except Exception as e:
            logger.error(f"Error toggling voice lock: {e}")
            return {"success": False, "message": str(e)}

    def set_voice_lock_threshold(self, threshold: float) -> Dict[str, Any]:
        """Updates the cosine similarity threshold (e.g. 0.70)."""
        try:
            th = max(0.40, min(0.95, float(threshold)))
            profile_manager.set("voice_lock_threshold", th)
            return {"success": True, "threshold": th}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _get_enrollment_audio(self, duration: float) -> np.ndarray:
        """
        Captures audio via the running SpeechStreamer (same device/gain as live
        verification) if available, otherwise falls back to sd.rec().
        """
        try:
            # Prefer the already-running InputStream so enrollment and
            # live verification share an identical audio path.
            from speech.streamer import speech_streamer
            if speech_streamer is not None and hasattr(speech_streamer, 'capture_enrollment_audio'):
                logger.info(f"Capturing enrollment via active stream ({duration}s)...")
                return speech_streamer.capture_enrollment_audio(duration=duration)
        except Exception as e:
            logger.warning(f"Streamer capture unavailable, falling back to sd.rec(): {e}")
        # Fallback: direct mic recording
        logger.info(f"Capturing enrollment via sd.rec ({duration}s)...")
        recording = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype='float32')
        sd.wait()
        return recording.flatten()

    def record_voice_enrollment_sample(self) -> Dict[str, Any]:
        """
        Records 3.0 seconds from the microphone (using the same audio path as live
        speaker verification) and extracts a voice embedding enrollment sample.
        """
        try:
            audio = self._get_enrollment_audio(duration=3.0)
            rms = float(np.sqrt(np.mean(audio**2)))
            if rms < 0.005:
                return {
                    "success": False,
                    "message": "Audio volume too low — please speak louder into your microphone.",
                    "count": len(voice_authenticator.temp_enrollment_samples)
                }
            logger.info(f"Enrollment sample RMS={rms:.4f}. Extracting embedding...")
            res = voice_authenticator.enroll_sample(audio)
            return res
        except Exception as e:
            logger.error(f"Error during enrollment recording: {e}")
            return {"success": False, "message": str(e), "count": len(voice_authenticator.temp_enrollment_samples)}

    def finalize_voice_enrollment(self) -> Dict[str, Any]:
        """
        Averages all recorded samples, creates master profile, and enables Voice Lock.
        """
        try:
            user_name = profile_manager.get("user_name", "Owner")
            success = voice_authenticator.save_profile(owner_name=user_name)
            if success:
                profile_manager.set("voice_lock_enabled", True)
                return {
                    "success": True,
                    "message": "Voice profile successfully enrolled and activated!"
                }
            return {
                "success": False,
                "message": "Could not finalize voice profile. Please record 3 samples first."
            }
        except Exception as e:
            logger.error(f"Error finalizing voice enrollment: {e}")
            return {"success": False, "message": str(e)}

    def reset_voice_enrollment(self) -> Dict[str, Any]:
        """Clears the master voice profile and disables Voice Lock."""
        try:
            voice_authenticator.clear_profile()
            profile_manager.set("voice_lock_enabled", False)
            return {"success": True, "message": "Voice profile deleted successfully."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def test_voice_match(self) -> Dict[str, Any]:
        """
        Records 3.0 seconds of live speech (via same audio path as live verification)
        and computes real-time similarity score against the master voice profile.
        """
        try:
            audio = self._get_enrollment_audio(duration=3.0)
            rms = float(np.sqrt(np.mean(audio**2)))
            if rms < 0.005:
                return {
                    "success": False,
                    "message": "Audio too quiet. Speak clearly into the microphone.",
                    "score": 0.0,
                    "is_match": False
                }

            threshold = float(profile_manager.get("voice_lock_threshold", 0.50))
            is_match, score = voice_authenticator.verify_speaker(audio, threshold=threshold)
            return {
                "success": True,
                "score": round(score, 3),
                "threshold": threshold,
                "is_match": is_match,
                "message": f"Match Score: {int(score * 100)}% ({'MATCH ✅ — Owner Verified' if is_match else 'NO MATCH ❌ — Access Denied'})"
            }
        except Exception as e:
            logger.error(f"Error testing voice match: {e}")
            return {"success": False, "score": 0.0, "is_match": False, "message": str(e)}

    # ---------------- System Utilities ---------------- #

    def open_external_url(self, url: str) -> bool:
        """Safely opens an external URL in the default browser."""
        try:
            if url.startswith("http://") or url.startswith("https://"):
                os.startfile(url)
                return True
        except Exception as e:
            logger.error(f"Failed to open URL {url}: {e}")
        return False

    # ---------------- CUDA & Acceleration Setup ---------------- #

    def get_cuda_status(self) -> Dict[str, Any]:
        """Returns full CUDA detection and acceleration status."""
        try:
            from utils.cuda_manager import get_cuda_status
            return get_cuda_status()
        except Exception as e:
            logger.error(f"Error getting CUDA status: {e}")
            return {"has_gpu": False, "has_cuda_dlls": False, "is_ready": False, "error": str(e)}

    def start_cuda_download(self) -> Dict[str, Any]:
        """Starts asynchronous download & installation of CUDA runtime DLLs."""
        try:
            from utils.cuda_manager import start_cuda_runtime_download
            return start_cuda_runtime_download()
        except Exception as e:
            logger.error(f"Error starting CUDA download: {e}")
            return {"success": False, "message": str(e)}

    def get_cuda_download_progress(self) -> Dict[str, Any]:
        """Returns the current progress of CUDA runtime download."""
        try:
            from utils.cuda_manager import get_download_progress
            return get_download_progress()
        except Exception as e:
            return {"is_downloading": False, "progress": 0, "error": str(e)}

    def close_window(self):
        """Closes the dashboard window."""
        if hasattr(self, "_window") and self._window:
            self._window.destroy()


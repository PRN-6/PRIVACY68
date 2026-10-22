import os
import logging
import platform
import shutil
import subprocess
from typing import Dict, Any, List

logger = logging.getLogger("PRIVACY68.DashboardBridge")


class _LazyProxy:
    """
    Defers importing a module until one of its attributes is first touched.

    The Control Center used to import the whole speech stack (ONNX Runtime,
    SciPy, HuggingFace Hub, faster-whisper) plus the plugin catalogue at
    import time, which added seconds to every dashboard launch even though
    none of it is needed until the user opens a specific tab.
    """

    def __init__(self, module_path: str, attribute: str):
        self._module_path = module_path
        self._attribute = attribute
        self._resolved = None

    def _resolve(self):
        if self._resolved is None:
            import importlib
            self._resolved = getattr(importlib.import_module(self._module_path), self._attribute)
        return self._resolved

    def __getattr__(self, item):
        return getattr(self._resolve(), item)


plugin_manager = _LazyProxy("plugins.manager", "plugin_manager")
profile_manager = _LazyProxy("plugins.profile_manager", "profile_manager")
voice_authenticator = _LazyProxy("speech.voice_auth", "voice_authenticator")


class DashboardAPI:
    """
    Python-to-JavaScript IPC Bridge.
    All public methods in this class are accessible inside the WebView window
    via `window.pywebview.api.<method_name>()`.
    """
    def __init__(self, window=None):
        self._window = window
        self._capture_streamer = None

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
                "llm_provider": profile_manager.get("llm_provider", "ollama"),
                "llm_model": profile_manager.get("llm_model", "qwen2.5:0.5b"),
                "api_key": profile_manager.get("api_key", ""),
                "api_base_url": profile_manager.get("api_base_url", ""),
                "cloud_model": profile_manager.get("cloud_model", "gpt-4o-mini"),
                "hud_enabled": bool(profile_manager.get("hud_enabled", True)),
                "theme": profile_manager.get("theme", "obsidian_red"),
                "voice_lock_enabled": bool(profile_manager.get("voice_lock_enabled", False)),
                "voice_lock_threshold": float(profile_manager.get("voice_lock_threshold", 0.50)),
            }
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return {}

    def test_llm_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Tests connection to Local Ollama or Cloud API Key (OpenAI / Groq / Custom)."""
        provider = data.get("provider", "ollama").lower()
        api_key = data.get("api_key", "").strip()
        model = data.get("model", "").strip()

        if provider == "ollama":
            try:
                import ollama
                res = ollama.list()
                models = [m.get("model", "") or m.get("name", "") for m in getattr(res, "models", [])]
                return {
                    "success": True,
                    "message": f"Connected to local Ollama! Found {len(models)} model(s)."
                }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Failed to connect to local Ollama: {e}"
                }

        # Cloud validation
        if not api_key:
            return {"success": False, "message": "Please enter an API Key to test."}

        import urllib.request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "PRIVACY68/1.0",
        }
        if provider in ("claude", "anthropic"):
            endpoint = "https://api.anthropic.com/v1/models"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "PRIVACY68/1.0",
            }
        elif provider == "groq":
            endpoint = "https://api.groq.com/openai/v1/models"
        elif provider in ("gemini", "google"):
            endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/models"
        elif provider == "openrouter":
            endpoint = "https://openrouter.ai/api/v1/models"
        elif provider == "openai":
            endpoint = "https://api.openai.com/v1/models"
        else:
            base = data.get("base_url", "").strip() or "https://api.openai.com/v1"
            endpoint = f"{base.rstrip('/')}/models"

        req = urllib.request.Request(
            endpoint,
            headers=headers,
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=6) as res:
                if res.status == 200:
                    return {
                        "success": True,
                        "message": f"Successfully authenticated with {provider.upper()} Cloud API!"
                    }
                return {"success": False, "message": f"HTTP status: {res.status}"}
        except Exception as e:
            return {"success": False, "message": f"Authentication failed: {e}"}

    def get_available_llm_models(self) -> List[Dict[str, Any]]:
        """Returns a list of all models installed in local Ollama instance."""
        try:
            import ollama
            res = ollama.list()
            models_list = []
            raw_models = getattr(res, 'models', []) if not isinstance(res, dict) else res.get('models', [])
            for m in raw_models:
                name = m.get('model') if isinstance(m, dict) else getattr(m, 'model', None) or getattr(m, 'name', None)
                size = m.get('size') if isinstance(m, dict) else getattr(m, 'size', None)
                if name:
                    models_list.append({
                        "name": name,
                        "size_mb": round(size / (1024 * 1024), 1) if size else None
                    })
            if not models_list:
                models_list = [{"name": "qwen2.5:0.5b", "size_mb": 397}]
            return models_list
        except Exception as e:
            logger.warning(f"Failed to query Ollama models: {e}")
            return [{"name": "qwen2.5:0.5b", "size_mb": 397}]

    def pull_llm_model(self, model_name: str) -> Dict[str, Any]:
        """Pulls a new model via Ollama."""
        try:
            import ollama
            clean_name = model_name.strip()
            if not clean_name:
                return {"success": False, "message": "Model name cannot be empty."}
            logger.info(f"Pulling model: {clean_name}")
            ollama.pull(clean_name)
            return {"success": True, "message": f"Successfully pulled {clean_name}"}
        except Exception as e:
            logger.error(f"Failed to pull {model_name}: {e}")
            return {"success": False, "message": str(e)}

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
        """Returns a list of all installed plugins with complete command and category metadata."""
        try:
            # Hot-detect any external plugins added, modified, or dropped into folders
            plugin_manager.check_and_reload_if_changed()
            plugins = plugin_manager.get_all_plugins()
            result = []
            for p in plugins:
                # Gather all actions, descriptions, and trigger phrases
                commands_info = []
                all_triggers = []
                for action_key, phrases in getattr(p, "fast_intents", {}).items():
                    desc = getattr(p, "descriptions", {}).get(action_key, f"Executes {action_key}")
                    if ":" in desc:
                        desc = desc.split(":", 1)[1].strip()
                    commands_info.append({
                        "action": action_key,
                        "description": desc,
                        "triggers": phrases
                    })
                    if phrases:
                        all_triggers.extend(phrases[:2])

                # Determine category & plugin_type
                category = getattr(p, "category", "")
                plugin_type = getattr(p, "plugin_type", "")
                if not category or category == "General":
                    pid = getattr(p, "id", "").lower()
                    if pid in ("windows", "system", "windows_plugin", "system_plugin"):
                        category = "System"
                        plugin_type = "OS Controls"
                    elif pid in ("chrome", "brave", "edge", "firefox", "browser"):
                        category = "Browser"
                        plugin_type = "Browser Control"
                    elif pid in ("whatsapp", "telegram", "discord", "slack"):
                        category = "Communication"
                        plugin_type = "Messaging & Chat"
                    elif pid in ("vscode", "terminal", "git", "python", "ide"):
                        category = "Developer"
                        plugin_type = "IDE & Code"
                    elif pid in ("ppt", "powerpoint", "notepad", "word", "excel", "calculator"):
                        category = "Productivity"
                        plugin_type = "Office & Slides"
                    elif getattr(p, "is_builtin", False):
                        category = "System"
                        plugin_type = "Core Integration"
                    else:
                        category = "Custom"
                        plugin_type = "Custom Application"

                result.append({
                    "id": p.id,
                    "name": p.name,
                    "version": getattr(p, "version", "1.0.0"),
                    "description": p.description,
                    "icon": p.icon,
                    "is_enabled": bool(p.is_enabled),
                    "is_builtin": getattr(p, "is_builtin", False),
                    "category": category,
                    "plugin_type": plugin_type,
                    "triggers": all_triggers[:4],
                    "commands": commands_info,
                    "total_commands": len(commands_info)
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
                err_msg = getattr(plugin_manager, "last_error", None) or "Could not install plugin file."
                return {"success": False, "message": err_msg}
        except Exception as e:
            logger.error(f"Error installing plugin file: {e}")
            return {"success": False, "message": str(e)}

    # ---------------- Installed Applications ---------------- #

    def get_installed_apps(self, rescan: bool = False) -> List[Dict[str, str]]:
        """
        Returns the applications discovered on this computer.

        These are the applications the assistant can open by name, so the
        user can check that a program is actually there before saying
        "open <name>".
        """
        try:
            from core.apps import app_index

            if rescan:
                app_index.refresh()
                # Teach the fast lane about anything installed since startup.
                from actions.catalog import register_installed_apps

                added = register_installed_apps()
                logger.info(f"Rescan found {added} new applications.")

            return [
                {"name": e.name, "source": e.source, "command": e.command}
                for e in sorted(app_index.all(), key=lambda e: e.name.lower())
            ]
        except Exception as e:
            logger.error(f"Error listing installed applications: {e}")
            return []

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

        # faster-whisper — the version is read from the installed distribution
        # metadata so the check stays cheap; importing the package itself pulls
        # in ctranslate2 and costs seconds.
        try:
            from importlib.metadata import version as _pkg_version
            whisper_version = _pkg_version("faster-whisper")
            ai_checks.append({
                "name": "faster-whisper (ASR)",
                "status": "ok",
                "detail": f"Installed v{whisper_version} • High-speed Whisper Engine",
                "link": None
            })
        except Exception:
            ai_checks.append({
                "name": "faster-whisper (ASR)",
                "status": "fail",
                "detail": "Not installed in environment.",
                "link": None
            })

        sections.append({"title": "Core AI & Speech Engines", "icon": "cpu", "items": ai_checks})

        # 1b. Control Center runtime — the WebView2 runtime is what renders
        #     this very window, so a missing one is worth surfacing.
        try:
            from utils.webview2 import get_webview2_status
            webview2 = get_webview2_status()
            if webview2["installed"]:
                ui_checks = [{
                    "name": "Edge WebView2 Runtime",
                    "status": "ok",
                    "detail": f"Installed • Version {webview2['version']}",
                    "link": None
                }]
            else:
                ui_checks = [{
                    "name": "Edge WebView2 Runtime",
                    "status": "fail",
                    "detail": "Not installed — the Control Center needs it to render.",
                    "link": webview2["download_url"]
                }]
            sections.append({"title": "Control Center Runtime", "icon": "monitor", "items": ui_checks})
        except Exception as e:
            logger.debug(f"WebView2 diagnostics unavailable: {e}")

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
            import sounddevice as sd
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
            import numpy as np
            import sounddevice as sd
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

    # ---------------- Enrollment Microphone Capture ---------------- #

    def start_enrollment_capture(self) -> Dict[str, Any]:
        """
        Opens the enrollment capture stream on demand.

        The microphone is deliberately NOT opened when the Control Center
        starts: the assistant process already holds the input device, and
        opening a second stream on machines whose audio driver runs in
        exclusive mode blocks the dashboard indefinitely. The stream is
        therefore created only when the user actually visits the Voice
        Enrollment tab.
        """
        if self._capture_streamer is not None:
            return {"success": True, "already_active": True}

        try:
            from speech.streamer import SpeechStreamer, set_speech_streamer

            # capture_only=True: identical device/gain/blocksize as live
            # verification, but no second copy of the Whisper model.
            streamer = SpeechStreamer(capture_only=True)
            set_speech_streamer(streamer)
            streamer.stream.start()
            self._capture_streamer = streamer
            logger.info("Dashboard enrollment capture stream started (lazy).")
            return {"success": True, "already_active": False}
        except Exception as e:
            logger.warning(f"Could not start the enrollment capture stream: {e}")
            self._capture_streamer = None
            return {
                "success": False,
                "message": (
                    "Could not open the microphone. Another application may be "
                    "using it exclusively — close other recording apps and try again."
                ),
            }

    def stop_enrollment_capture(self) -> Dict[str, Any]:
        """Releases the enrollment capture stream when the user leaves the tab."""
        streamer = self._capture_streamer
        if streamer is None:
            return {"success": True, "active": False}
        try:
            stream = getattr(streamer, "stream", None)
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception as e:
            logger.debug(f"stop_enrollment_capture: {e}")
        finally:
            self._capture_streamer = None
            logger.info("Dashboard enrollment capture stream stopped.")
        return {"success": True, "active": False}

    def _get_enrollment_audio(self, duration: float) -> "np.ndarray":
        """
        Captures audio via the running SpeechStreamer (same device/gain as live
        verification) if available, otherwise falls back to sd.rec().
        """
        import numpy as np
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
        import sounddevice as sd
        logger.info(f"Capturing enrollment via sd.rec ({duration}s)...")
        recording = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype='float32')
        sd.wait()
        return recording.flatten()

    def record_voice_enrollment_sample(self) -> Dict[str, Any]:
        """
        Records 3.0 seconds from the microphone (using the same audio path as live
        speaker verification) and extracts a voice embedding enrollment sample.
        """
        import numpy as np
        try:
            # Make sure the capture stream exists before recording.
            if self._capture_streamer is None:
                started = self.start_enrollment_capture()
                if not started.get("success"):
                    return {
                        "success": False,
                        "message": started.get("message", "Microphone is unavailable."),
                        "count": len(voice_authenticator.temp_enrollment_samples),
                    }

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
            import numpy as np
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
                from core.platform import open_uri

                return open_uri(url)
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


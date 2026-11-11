import os
import logging
import platform
import shutil
import subprocess
from typing import Dict, Any, List
import sounddevice as sd
import numpy as np

from plugins.manager import plugin_manager
from plugins.profile_manager import profile_manager

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
                "assistant_name": profile_manager.get("assistant_name", "Alexa"),
                "wake_word": profile_manager.get("wake_word", "alexa"),
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

    def check_ollama_status(self) -> Dict[str, Any]:
        """
        Checks if Ollama is installed on the computer and whether its service is running.
        """
        ollama_path = shutil.which("ollama")
        if not ollama_path:
            local_app_data = os.getenv("LOCALAPPDATA", "")
            cand = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
            if os.path.isfile(cand):
                ollama_path = cand
            else:
                cand_pf = os.path.join(os.getenv("ProgramFiles", "C:\\Program Files"), "Ollama", "ollama.exe")
                if os.path.isfile(cand_pf):
                    ollama_path = cand_pf

        installed = bool(ollama_path)
        running = False
        models = []
        version = None

        import urllib.request
        import json
        import config

        ollama_base = getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ollama_base = ollama_base.rstrip("/")
        headers = {"User-Agent": "PRIVACY68/1.0"}
        ollama_key = getattr(config, "OLLAMA_API_KEY", "") or os.environ.get("OLLAMA_API_KEY", "")
        if ollama_key:
            headers["Authorization"] = f"Bearer {ollama_key.strip()}"

        try:
            req = urllib.request.Request(f"{ollama_base}/api/tags", headers=headers)
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    running = True
                    data = json.loads(resp.read().decode("utf-8"))
                    for item in data.get("models", []):
                        name = item.get("name") or item.get("model")
                        if name:
                            models.append(name)
        except Exception:
            running = False

        if running:
            installed = True
            try:
                req_ver = urllib.request.Request(f"{ollama_base}/api/version", headers=headers)
                with urllib.request.urlopen(req_ver, timeout=1.0) as resp:
                    if resp.status == 200:
                        ver_data = json.loads(resp.read().decode("utf-8"))
                        version = ver_data.get("version")
            except Exception:
                pass

        if running:
            status_text = "running"
            message = f"Ollama is running with {len(models)} model(s) installed."
        elif installed:
            status_text = "offline"
            message = "Ollama is installed on this computer, but the background service is not running."
        else:
            status_text = "not_installed"
            message = "Ollama is not installed on this computer."

        return {
            "installed": installed,
            "running": running,
            "executable_path": ollama_path,
            "models": models,
            "version": version,
            "status_text": status_text,
            "message": message,
        }

    def start_ollama(self) -> Dict[str, Any]:
        """Attempts to start the Ollama service on the local computer."""
        try:
            status = self.check_ollama_status()
            if status.get("running"):
                return {"success": True, "message": "Ollama is already running."}

            ollama_path = status.get("executable_path")
            if not ollama_path:
                ollama_path = shutil.which("ollama")

            if not ollama_path:
                return {"success": False, "message": "Ollama is not installed. Download it from ollama.com."}

            app_dir = os.path.dirname(ollama_path)
            app_exe = os.path.join(app_dir, "ollama app.exe")
            if os.path.isfile(app_exe):
                subprocess.Popen([app_exe], shell=True)
            else:
                creationflags = 0x08000000 if platform.system() == "Windows" else 0
                subprocess.Popen([ollama_path, "serve"], creationflags=creationflags, close_fds=True)

            return {"success": True, "message": "Starting Ollama service..."}
        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")
            return {"success": False, "message": f"Could not start Ollama: {e}"}

    def get_runtime_status(self) -> Dict[str, Any]:
        """Returns status values read from the active runtime components."""
        try:
            from actions.agent_brain import agent_brain
            from config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE

            voice_status = self.get_voice_lock_status()
            cuda_status = self.get_cuda_status()
            return {
                "success": True,
                "model": agent_brain.model,
                "speech_model": WHISPER_MODEL_SIZE,
                "speech_device": WHISPER_DEVICE,
                "speech_compute_type": WHISPER_COMPUTE_TYPE,
                "voice_lock": voice_status,
                "cuda": cuda_status,
                "ollama": self.check_ollama_status(),
            }
        except Exception as e:
            logger.error(f"Error getting runtime status: {e}")
            return {"success": False, "message": str(e)}

    def test_llm_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Tests connection to Local Ollama, Cloud API Key, or Custom Endpoint."""
        provider = data.get("provider", "ollama").lower()
        api_key = data.get("api_key", "").strip()
        model = data.get("model", "").strip()
        base_url = data.get("base_url", "").strip()

        if provider == "ollama":
            import config
            ollama_base = base_url or getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            ollama_base = ollama_base.rstrip("/")
            headers = {"User-Agent": "PRIVACY68/1.0"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            try:
                import urllib.request
                import json
                req = urllib.request.Request(f"{ollama_base}/api/tags", headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=3.0) as res:
                    if res.status == 200:
                        tags_data = json.loads(res.read().decode("utf-8"))
                        models = [m.get("model", "") or m.get("name", "") for m in tags_data.get("models", [])]
                        return {
                            "success": True,
                            "message": f"Connected to Ollama at {ollama_base}! Found {len(models)} model(s)."
                        }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Failed to connect to Ollama at {ollama_base}: {e}"
                }

        # Cloud or Custom validation
        if not api_key and not base_url:
            return {"success": False, "message": "Please enter an API Key or Custom Base URL to test."}

        import urllib.request
        headers = {
            "User-Agent": "PRIVACY68/1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        data_body = None
        if provider in ("claude", "anthropic"):
            endpoint = "https://api.anthropic.com/v1/models"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "PRIVACY68/1.0",
            }
        elif provider == "groq":
            # Test with lightweight 1-token chat ping on active free model
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            headers["Content-Type"] = "application/json"
            data_body = json.dumps({"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}).encode("utf-8")
        elif provider in ("gemini", "google"):
            endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/models"
        elif provider == "openrouter":
            endpoint = "https://openrouter.ai/api/v1/models"
        elif provider == "openai":
            base = base_url or getattr(config, "OPENAI_API_BASE", "") or "https://api.openai.com/v1"
            endpoint = f"{base.rstrip('/')}/models"
        else:
            base = base_url or data.get("base_url", "").strip() or "https://api.openai.com/v1"
            endpoint = f"{base.rstrip('/')}/models"

        req = urllib.request.Request(
            endpoint,
            headers=headers,
            data=data_body,
            method="POST" if data_body else "GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=6) as res:
                if res.status == 200:
                    return {
                        "success": True,
                        "message": f"Successfully authenticated with {provider.upper()} API!"
                    }
                return {"success": False, "message": f"HTTP status: {res.status}"}
        except Exception as e:
            return {"success": False, "message": f"Authentication failed: {e}"}

    def save_api_key(self, provider: str, api_key: str, model: str = "", base_url: str = "") -> Dict[str, Any]:
        """Saves API key, base URL, and active model to .env and updates runtime config with smart provider auto-detection."""
        import config
        provider = provider.lower().strip()
        api_key = api_key.strip()
        base_url = base_url.strip()

        # Smart provider auto-detection if key matches standard prefixes
        if api_key.startswith("gsk_"):
            provider = "groq"
        elif api_key.startswith("AIzaSy") or api_key.startswith("AQ.Ab"):
            provider = "gemini"
        elif api_key.startswith("sk-or-"):
            provider = "openrouter"
        elif api_key.startswith("sk-ant-"):
            provider = "claude"

        key_var = None
        default_model = None
        if "gemini" in provider or "google" in provider:
            key_var = "GEMINI_API_KEY"
            config.GEMINI_API_KEY = api_key
            os.environ["GEMINI_API_KEY"] = api_key
            os.environ["GOOGLE_API_KEY"] = api_key
            default_model = "gemini/gemini-3.5-flash"
        elif "groq" in provider:
            key_var = "GROQ_API_KEY"
            config.GROQ_API_KEY = api_key
            os.environ["GROQ_API_KEY"] = api_key
            default_model = "groq/openai/gpt-oss-120b"
        elif "openrouter" in provider:
            key_var = "OPENROUTER_API_KEY"
            config.OPENROUTER_API_KEY = api_key
            os.environ["OPENROUTER_API_KEY"] = api_key
            default_model = "openrouter/google/gemini-2.0-flash-exp:free"
        elif "claude" in provider or "anthropic" in provider:
            key_var = "ANTHROPIC_API_KEY"
            config.ANTHROPIC_API_KEY = api_key
            os.environ["ANTHROPIC_API_KEY"] = api_key
            default_model = "claude-3-5-sonnet-20241022"
        elif "openai" in provider:
            key_var = "OPENAI_API_KEY"
            config.OPENAI_API_KEY = api_key
            os.environ["OPENAI_API_KEY"] = api_key
            default_model = "openai/gpt-4o-mini"
        elif "ollama" in provider:
            key_var = "OLLAMA_API_KEY"
            config.OLLAMA_API_KEY = api_key
            os.environ["OLLAMA_API_KEY"] = api_key
            default_model = "ollama/qwen2.5-coder:7b"
        elif "custom" in provider:
            key_var = "CUSTOM_API_KEY"
            config.CUSTOM_API_KEY = api_key
            os.environ["CUSTOM_API_KEY"] = api_key
            default_model = "openai/custom-model"

        if key_var:
            config.update_dotenv_var(key_var, api_key)

        if base_url:
            if "ollama" in provider:
                config.OLLAMA_BASE_URL = base_url
                os.environ["OLLAMA_BASE_URL"] = base_url
                config.update_dotenv_var("OLLAMA_BASE_URL", base_url)
            else:
                config.OPENAI_API_BASE = base_url
                config.CUSTOM_API_BASE = base_url
                os.environ["OPENAI_API_BASE"] = base_url
                os.environ["CUSTOM_API_BASE"] = base_url
                config.update_dotenv_var("OPENAI_API_BASE", base_url)
                config.update_dotenv_var("CUSTOM_API_BASE", base_url)

        chosen_model = model.strip() if model else default_model
        if chosen_model:
            config.AGENT_BRAIN_MODEL = chosen_model
            from actions.agent_brain import agent_brain
            agent_brain.model = chosen_model
            config.update_dotenv_var("AGENT_BRAIN_MODEL", chosen_model)

        return {"success": True, "message": f"{provider.capitalize()} settings saved successfully!"}

    def get_api_keys(self) -> Dict[str, Any]:
        """Returns configured status of Cloud API keys and active model."""
        import config
        return {
            "gemini": bool(getattr(config, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")),
            "groq": bool(getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")),
            "openrouter": bool(getattr(config, "OPENROUTER_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")),
            "claude": bool(getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")),
            "openai": bool(getattr(config, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or getattr(config, "CUSTOM_API_KEY", "")),
            "active_model": getattr(config, "AGENT_BRAIN_MODEL", "gemini/gemini-3.5-flash"),
        }

    def set_active_model(self, model: str) -> Dict[str, Any]:
        """Sets the active Agent Brain model in runtime and persists to .env."""
        try:
            import config
            model = model.strip()
            if not model:
                return {"success": False, "message": "Model identifier cannot be empty."}
            config.AGENT_BRAIN_MODEL = model
            from actions.agent_brain import agent_brain
            agent_brain.model = model
            config.update_dotenv_var("AGENT_BRAIN_MODEL", model)
            return {"success": True, "message": f"Active model set to '{model}'", "model": model}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_api_keys_detail(self) -> Dict[str, Any]:
        """Returns detailed configuration status for all cloud AI providers and local LLMs."""
        import config

        def mask(k):
            if not k:
                return ""
            if len(k) <= 8:
                return k[:2] + "****"
            return k[:6] + "..." + k[-4:]

        gemini_k = getattr(config, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        groq_k = getattr(config, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        openrouter_k = getattr(config, "OPENROUTER_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
        claude_k = getattr(config, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        openai_k = getattr(config, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        custom_k = getattr(config, "CUSTOM_API_KEY", "") or os.environ.get("CUSTOM_API_KEY", "")
        openai_base = getattr(config, "OPENAI_API_BASE", "") or getattr(config, "CUSTOM_API_BASE", "")
        ollama_url = getattr(config, "OLLAMA_BASE_URL", "") or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ollama_status = self.check_ollama_status()

        return {
            "active_model": getattr(config, "AGENT_BRAIN_MODEL", "gemini/gemini-3.5-flash"),
            "gemini": {
                "configured": bool(gemini_k),
                "preview": mask(gemini_k),
                "model": "gemini/gemini-3.5-flash"
            },
            "groq": {
                "configured": bool(groq_k),
                "preview": mask(groq_k),
                "model": "groq/openai/gpt-oss-120b"
            },
            "openrouter": {
                "configured": bool(openrouter_k),
                "preview": mask(openrouter_k),
                "model": "openrouter/google/gemini-2.0-flash-exp:free"
            },
            "claude": {
                "configured": bool(claude_k),
                "preview": mask(claude_k),
                "model": "claude-3-5-sonnet-20241022"
            },
            "openai": {
                "configured": bool(openai_k or custom_k or openai_base),
                "preview": mask(openai_k or custom_k),
                "base_url": openai_base,
                "model": "openai/gpt-4o-mini"
            },
            "ollama": {
                "installed": ollama_status.get("installed", False),
                "running": ollama_status.get("running", False),
                "models": ollama_status.get("models", []),
                "base_url": ollama_url,
            }
        }

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns all crystallized skills learned by PRIVACY68."""
        try:
            from actions.skill_manager import skill_manager
            return skill_manager.list_skills()
        except Exception as e:
            logger.warning(f"Error listing skills: {e}")
            return []

    def run_skill(self, skill_id: str) -> Dict[str, Any]:
        """Executes a crystallized skill by ID."""
        try:
            from actions.skill_manager import skill_manager
            for s in skill_manager.list_skills():
                if s.get("id") == skill_id:
                    res = skill_manager.execute_skill(s)
                    if res.get("success"):
                        skill_manager.record_execution(skill_id, success=True)
                    return res
            return {"success": False, "message": f"Skill '{skill_id}' not found."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        """Deletes a learned skill."""
        try:
            from actions.skill_manager import skill_manager
            ok = skill_manager.delete_skill(skill_id)
            return {"success": ok, "message": "Skill removed." if ok else "Skill not found or protected."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def record_voice_command(self) -> Dict[str, Any]:
        """Records on-demand voice from the microphone and returns transcribed text."""
        try:
            from speech.streamer import PushToTalkRecorder, autocorrect_speech_command
            import time
            recorder = PushToTalkRecorder()
            recorder.start()
            time.sleep(3.2)
            raw_text = recorder.stop_and_transcribe()
            text = autocorrect_speech_command(raw_text) if raw_text else ""
            if text:
                return {"success": True, "text": text}
            return {"success": False, "message": "No speech detected in audio sample."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_remote_server_info(self) -> Dict[str, Any]:
        """Returns Mobile Web Remote server access URL, IP, and status."""
        try:
            from server.remote_server import get_remote_url, get_local_ip
            import config
            port = getattr(config, "REMOTE_SERVER_PORT", 8765)
            enabled = getattr(config, "ENABLE_REMOTE_SERVER", True)
            local_ip = get_local_ip()
            url = get_remote_url(port)
            return {
                "enabled": enabled,
                "port": port,
                "local_ip": local_ip,
                "url": url,
                "message": f"Connect any phone/tablet on your Wi-Fi to {url}"
            }
        except Exception as e:
            logger.error(f"Error getting remote server info: {e}")
            return {"enabled": False, "port": 8765, "local_ip": "127.0.0.1", "url": "http://127.0.0.1:8765", "error": str(e)}

    def get_security_guard_info(self) -> Dict[str, Any]:
        """Returns 3-tier security model status and recent audit log entries."""
        import time
        try:
            from computer_use.security_guard import security_guard
            audit = []
            for entry in getattr(security_guard, "_audit_log", [])[-15:]:
                audit.append({
                    "action": str(entry.get("action", "")),
                    "risk_level": str(entry.get("risk_level", "SAFE")).replace("ActionRiskLevel.", ""),
                    "timestamp": time.strftime("%H:%M:%S", time.localtime(entry.get("timestamp", time.time()))),
                    "approved": bool(entry.get("approved", True)),
                })
            rules_summary = {
                "safe_count": sum(1 for v in security_guard._action_risk_rules.values() if v.value == 1),
                "sensitive_count": sum(1 for v in security_guard._action_risk_rules.values() if v.value == 2),
                "critical_count": sum(1 for v in security_guard._action_risk_rules.values() if v.value == 3),
            }
            has_pending = security_guard.check_has_pending()
            pending_desc = ""
            if has_pending and security_guard._pending_action:
                pending_desc = security_guard._pending_action.description
            return {
                "has_pending": has_pending,
                "pending_description": pending_desc,
                "rules_summary": rules_summary,
                "audit_log": audit,
            }
        except Exception as e:
            logger.error(f"Error getting security guard info: {e}")
            return {"has_pending": False, "audit_log": [], "rules_summary": {"safe_count": 14, "sensitive_count": 13, "critical_count": 4}}

    def confirm_pending_security_action(self, confirmed: bool) -> Dict[str, Any]:
        """Confirms or cancels a pending Sensitive Level 2 action."""
        try:
            from computer_use.security_guard import security_guard
            if confirmed:
                res = security_guard.confirm_pending()
                return {"success": True, "message": "Action confirmed and executed.", "result": str(res)}
            else:
                security_guard.cancel_pending()
                return {"success": True, "message": "Action cancelled safely."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def execute_system_quick_action(self, action_name: str) -> Dict[str, Any]:
        """Executes instant predefined desktop actions directly with 0ms latency."""
        import ctypes
        import subprocess
        action = action_name.lower().strip()
        try:
            if action == "mute":
                ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
                return {"success": True, "message": "Toggled volume mute."}
            elif action == "volume_up":
                for _ in range(5):
                    ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
                return {"success": True, "message": "Increased volume."}
            elif action == "volume_down":
                for _ in range(5):
                    ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
                return {"success": True, "message": "Decreased volume."}
            elif action == "lock":
                ctypes.windll.user32.LockWorkStation()
                return {"success": True, "message": "Locked Windows workstation."}
            elif action == "notepad":
                subprocess.Popen(["notepad.exe"])
                return {"success": True, "message": "Launched Notepad."}
            elif action == "calc":
                subprocess.Popen(["calc.exe"])
                return {"success": True, "message": "Launched Calculator."}
            elif action == "taskmgr":
                subprocess.Popen(["taskmgr.exe"])
                return {"success": True, "message": "Launched Task Manager."}
            elif action == "explorer":
                subprocess.Popen(["explorer.exe"])
                return {"success": True, "message": "Opened File Explorer."}
            elif action == "screenshot":
                return self.run_skill("take_screenshot")
            elif action == "diagnostics":
                return self.run_skill("system_performance_diagnostics")
            elif action == "downloads":
                return self.run_skill("organize_downloads")
            else:
                from actions.executor import execute_system_command_detailed
                return execute_system_command_detailed(action)
        except Exception as e:
            return {"success": False, "message": str(e)}

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

    # ---------------- GitHub Integration ---------------- #

    def get_github_status(self) -> Dict[str, Any]:
        try:
            from plugins.github_plugin import GitHubPlugin
            return {"success": True, **GitHubPlugin().get_connection_status()}
        except Exception as e:
            logger.error("Error checking GitHub connection: %s", e)
            return {"success": False, "message": str(e), "connected": False}

    def connect_github(self, token: str) -> Dict[str, Any]:
        try:
            from plugins.github_plugin import GitHubPlugin
            return GitHubPlugin().connect(token)
        except Exception as e:
            logger.error("Error connecting GitHub account: %s", e)
            return {"success": False, "message": str(e)}

    def disconnect_github(self) -> Dict[str, Any]:
        try:
            from plugins.github_plugin import GitHubPlugin
            return GitHubPlugin().disconnect()
        except Exception as e:
            logger.error("Error disconnecting GitHub account: %s", e)
            return {"success": False, "message": str(e)}

    # ---------------- Gmail Integration ---------------- #

    def get_gmail_config(self) -> Dict[str, Any]:
        """Returns the configured Gmail sender/account email."""
        try:
            from plugins.manager import plugin_manager
            plugin = plugin_manager.get_plugin("gmail")
            email = plugin.get_user_email() if plugin and hasattr(plugin, "get_user_email") else profile_manager.get("gmail_user_email", "")
            return {"success": True, "email": email}
        except Exception as e:
            logger.error(f"Error getting Gmail config: {e}")
            return {"success": False, "email": "", "message": str(e)}

    def set_gmail_config(self, email: str) -> Dict[str, Any]:
        """Saves the user's Gmail address to preferences."""
        try:
            clean_email = email.strip()
            from plugins.manager import plugin_manager
            plugin = plugin_manager.get_plugin("gmail")
            if plugin and hasattr(plugin, "set_user_email"):
                plugin.set_user_email(clean_email)
            else:
                profile_manager.set("gmail_user_email", clean_email)
            logger.info(f"Updated Gmail account email to '{clean_email}'")
            return {"success": True, "email": clean_email, "message": f"Gmail account saved as '{clean_email}'"}
        except Exception as e:
            logger.error(f"Error setting Gmail config: {e}")
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
                for action_key, phrases in (getattr(p, "fast_intents", None) or {}).items():
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
                    elif pid in ("whatsapp", "telegram", "discord", "slack", "gmail"):
                        category = "Communication"
                        plugin_type = "Messaging & Email"
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
                    "id": getattr(p, "id", p.__class__.__name__.lower()),
                    "name": getattr(p, "name", p.__class__.__name__),
                    "version": getattr(p, "version", "1.0.0"),
                    "description": getattr(p, "description", "No description provided."),
                    "icon": getattr(p, "icon", "🔌"),
                    "is_enabled": bool(getattr(p, "is_enabled", True)),
                    "is_builtin": getattr(p, "is_builtin", False),
                    "category": category,
                    "plugin_type": plugin_type,
                    "user_email": getattr(p, "get_user_email", lambda: "")() if hasattr(p, "get_user_email") else "",
                    "triggers": all_triggers[:4],
                    "commands": commands_info,
                    "total_commands": len(commands_info)
                })
            return result
        except Exception as e:
            logger.error(f"Error getting plugins: {e}")
            raise

    def toggle_plugin(self, plugin_id: str, enabled: bool) -> Dict[str, Any]:
        """Enables or disables a specific plugin."""
        try:
            if not plugin_manager.set_plugin_enabled(plugin_id, enabled):
                return {"success": False, "message": f"Plugin '{plugin_id}' was not found."}
            return {"success": True, "plugin_id": plugin_id, "enabled": enabled}
        except Exception as e:
            logger.error(f"Error toggling plugin {plugin_id}: {e}")
            return {"success": False, "message": str(e)}

    def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstalls and deletes a custom user plugin."""
        try:
            plugin = plugin_manager.get_plugin(plugin_id)
            if not plugin:
                return {"success": False, "message": f"Plugin '{plugin_id}' was not found."}
            if getattr(plugin, "is_builtin", False):
                return {"success": False, "message": "Built-in plugins cannot be uninstalled."}
            success = plugin_manager.uninstall_plugin(plugin_id)
            if success:
                return {"success": True, "message": f"Plugin '{plugin_id}' uninstalled."}
            return {"success": False, "message": "The plugin file could not be removed."}
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

    def pick_plugin_file(self) -> Dict[str, Any]:
        """Opens native file picker to select a Python plugin."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                title="Select PRIVACY68 Plugin File",
                filetypes=[("Python plugin files", "*.py")]
            )
            root.destroy()
            return {"success": True, "file_path": file_path or ""}
        except Exception as e:
            logger.error(f"Error opening file dialog: {e}")
            return {"success": False, "message": str(e)}

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
                "detail": "Ollama not installed (optional). Use Cloud APIs (Gemini/Groq/OpenRouter) or install Ollama for offline models.",
                "link": "https://ollama.com/download"
            })

        # Google Web Speech Recognition
        try:
            import speech_recognition as sr
            ai_checks.append({
                "name": "Google Web Speech (ASR)",
                "status": "ok",
                "detail": f"SpeechRecognition v{getattr(sr, '__version__', '3.10+')} • Free Cloud Voice Engine",
                "link": None
            })
        except ImportError:
            ai_checks.append({
                "name": "Google Web Speech (ASR)",
                "status": "fail",
                "detail": "SpeechRecognition library not installed.",
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

    # ---------------- Voice Lock (Removed) ---------------- #

    def get_voice_lock_status(self) -> Dict[str, Any]:
        return {"enabled": False, "is_enrolled": False, "threshold": 0.50, "model_ready": False}

    def toggle_voice_lock(self, enabled: bool) -> Dict[str, Any]:
        return {"success": True, "enabled": False}

    def set_voice_lock_threshold(self, threshold: float) -> Dict[str, Any]:
        return {"success": True, "threshold": 0.50}

    def record_voice_enrollment_sample(self) -> Dict[str, Any]:
        return {"success": False, "message": "Voice Lock feature has been removed."}

    def finalize_voice_enrollment(self) -> Dict[str, Any]:
        return {"success": False, "message": "Voice Lock feature has been removed."}

    def reset_voice_enrollment(self) -> Dict[str, Any]:
        return {"success": True, "message": "Voice profile cleared."}

    def test_voice_match(self) -> Dict[str, Any]:
        return {"success": False, "score": 0.0, "is_match": False, "message": "Voice Lock feature has been removed."}

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

    def execute_command(self, text: str) -> Dict[str, Any]:
        """
        Executes a natural-language command through the standard action executor.
        This method is called from the Dashboard's Neural Console.
        """
        try:
            from actions.executor import execute_system_command_detailed
            from actions.agent_brain import agent_brain

            result = execute_system_command_detailed(text)
            response = dict(result)
            if response.get("method") == "agentic_engine":
                response["reasoning"] = getattr(agent_brain, "last_reasoning", "")
                response["code"] = getattr(agent_brain, "last_code", "")
            else:
                response.setdefault("reasoning", response.get("message", ""))
                response.setdefault("code", "")
            return response
        except Exception as e:
            logger.error(f"Error executing command from dashboard: {e}")
            return {"success": False, "message": str(e)}

    def close_app(self):
        """Closes the dashboard window."""
        if hasattr(self, "_window") and self._window:
            self._window.destroy()

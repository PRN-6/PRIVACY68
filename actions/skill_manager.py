"""
PRIVACY68 Skill Manager
Autonomous self-improving skill acquisition and fast-path execution loop.
Learns working Python automations from the Agent Brain and crystallizes them into local,
zero-latency, zero-cost skills that run deterministically without calling LLM APIs.
"""

import os
import re
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from actions.agent_runner import run_agent_code

logger = logging.getLogger("PRIVACY68.SkillManager")

# Stop words to exclude when extracting distinctive keywords from commands
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "by", "with",
    "is", "it", "this", "that", "my", "me", "your", "please", "can", "you", "could",
    "would", "i", "want", "need", "just", "now", "do", "make", "get", "run", "start"
})

# Pre-seeded starter skills providing immediate out-of-the-box utility
PRESEEDED_SKILLS = [
    {
        "id": "organize_downloads",
        "name": "Organize Downloads Folder",
        "description": "Categorizes and organizes unorganized files in the user's Downloads folder into subdirectories by extension.",
        "trigger_phrases": [
            "organize downloads",
            "organize my downloads",
            "organize downloads folder",
            "sort downloads",
            "clean downloads folder",
            "organize downloads by file type"
        ],
        "keywords": ["organize", "downloads", "folder", "sort", "clean", "extension"],
        "code": (
            "import os, shutil\n"
            "from pathlib import Path\n"
            "\n"
            "# Resolve Downloads folder\n"
            "home = Path.home()\n"
            "onedrive = os.environ.get('OneDrive') or os.environ.get('OneDriveConsumer') or ''\n"
            "dl_path = Path(onedrive) / 'Downloads' if onedrive and (Path(onedrive) / 'Downloads').exists() else home / 'Downloads'\n"
            "\n"
            "if not dl_path.exists():\n"
            "    print(f'Downloads folder not found at {dl_path}')\n"
            "else:\n"
            "    CATEGORIES = {\n"
            "        'Images': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'},\n"
            "        'Documents': {'.pdf', '.docx', '.doc', '.txt', '.pptx', '.xlsx', '.csv', '.md'},\n"
            "        'Audio': {'.mp3', '.wav', '.flac', '.m4a', '.ogg'},\n"
            "        'Video': {'.mp4', '.mkv', '.mov', '.avi', '.webm'},\n"
            "        'Archives': {'.zip', '.rar', '.7z', '.tar', '.gz'},\n"
            "        'Code': {'.py', '.js', '.html', '.css', '.json', '.cpp', '.java', '.ts'},\n"
            "        'Installers': {'.exe', '.msi', '.iso'}\n"
            "    }\n"
            "    moved = 0\n"
            "    for item in list(dl_path.iterdir()):\n"
            "        if item.is_file() and not item.name.startswith('.'):\n"
            "            ext = item.suffix.lower()\n"
            "            target_folder = 'Other'\n"
            "            for cat_name, extensions in CATEGORIES.items():\n"
            "                if ext in extensions:\n"
            "                    target_folder = cat_name\n"
            "                    break\n"
            "            target_dir = dl_path / target_folder\n"
            "            target_dir.mkdir(exist_ok=True)\n"
            "            dest = target_dir / item.name\n"
            "            if not dest.exists():\n"
            "                try:\n"
            "                    shutil.move(str(item), str(dest))\n"
            "                    moved += 1\n"
            "                except Exception:\n"
            "                    pass\n"
            "    print(f'Downloads organized: sorted {moved} files into categorized folders.')\n"
        ),
        "success_count": 1,
        "is_builtin": True
    },
    {
        "id": "take_screenshot",
        "name": "Capture Desktop Screenshot",
        "description": "Takes a full-screen screenshot and saves it directly to the user's Desktop with a timestamp.",
        "trigger_phrases": [
            "take a screenshot",
            "take screenshot",
            "capture screen",
            "capture screenshot",
            "save screenshot to desktop",
            "screenshot"
        ],
        "keywords": ["take", "screenshot", "capture", "screen", "desktop"],
        "code": (
            "import os, time\n"
            "from pathlib import Path\n"
            "try:\n"
            "    from PIL import ImageGrab\n"
            "except ImportError:\n"
            "    import pyautogui as ImageGrab\n"
            "\n"
            "home = Path.home()\n"
            "onedrive = os.environ.get('OneDrive') or os.environ.get('OneDriveConsumer') or ''\n"
            "desktop = Path(onedrive) / 'Desktop' if onedrive and (Path(onedrive) / 'Desktop').exists() else home / 'Desktop'\n"
            "desktop.mkdir(exist_ok=True)\n"
            "\n"
            "timestamp = time.strftime('%Y%m%d_%H%M%S')\n"
            "filename = desktop / f'screenshot_{timestamp}.png'\n"
            "img = ImageGrab.grab()\n"
            "img.save(str(filename))\n"
            "print(f'Screenshot saved to {filename}')\n"
        ),
        "success_count": 1,
        "is_builtin": True
    },
    {
        "id": "system_performance_diagnostics",
        "name": "Check System Performance",
        "description": "Gathers and displays active OS version and system RAM utilization using Windows kernel diagnostics.",
        "trigger_phrases": [
            "check system performance",
            "system diagnostics",
            "check cpu and ram",
            "check memory usage",
            "check ram",
            "system status"
        ],
        "keywords": ["system", "performance", "diagnostics", "ram", "memory", "status"],
        "code": (
            "import os, platform, ctypes\n"
            "\n"
            "class MEMORYSTATUSEX(ctypes.Structure):\n"
            "    _fields_ = [\n"
            "        ('dwLength', ctypes.c_ulong),\n"
            "        ('dwMemoryLoad', ctypes.c_ulong),\n"
            "        ('ullTotalPhys', ctypes.c_ulonglong),\n"
            "        ('ullAvailPhys', ctypes.c_ulonglong),\n"
            "        ('ullTotalPageFile', ctypes.c_ulonglong),\n"
            "        ('ullAvailPageFile', ctypes.c_ulonglong),\n"
            "        ('ullTotalVirtual', ctypes.c_ulonglong),\n"
            "        ('ullAvailVirtual', ctypes.c_ulonglong),\n"
            "        ('sullAvailExtendedVirtual', ctypes.c_ulonglong),\n"
            "    ]\n"
            "\n"
            "stat = MEMORYSTATUSEX()\n"
            "stat.dwLength = ctypes.sizeof(stat)\n"
            "ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))\n"
            "total_gb = round(stat.ullTotalPhys / (1024**3), 1)\n"
            "used_gb = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 1)\n"
            "print(f'System Performance Diagnostics:\\n• OS: {platform.system()} {platform.release()} ({platform.machine()})\\n• RAM Usage: {stat.dwMemoryLoad}% ({used_gb} GB used / {total_gb} GB total)')\n"
        ),
        "success_count": 1,
        "is_builtin": True
    }
]


class SkillManager:
    """
    Manages autonomous skill learning, persistent storage, and fast-path recall.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            appdata = os.getenv("APPDATA", os.path.expanduser("~"))
            self.storage_dir = Path(appdata) / "PRIVACY68" / "skills"

        self.index_file = self.storage_dir / "learned_skills.json"
        self._ensure_storage()
        self.skills: Dict[str, Dict[str, Any]] = self._load_skills()

    def _ensure_storage(self) -> None:
        """Creates storage directories if not already present."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create skills directory {self.storage_dir}: {e}")

    def _load_skills(self) -> Dict[str, Dict[str, Any]]:
        """Loads learned skills from disk or seeds with built-in skills if missing."""
        skills: Dict[str, Dict[str, Any]] = {}

        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        skills = loaded
            except Exception as e:
                logger.error(f"Failed to read skills index: {e}")

        # Ensure preseeded skills exist in the registry
        updated = False
        for pre in PRESEEDED_SKILLS:
            sid = pre["id"]
            if sid not in skills:
                code_file = self.storage_dir / f"{sid}.py"
                try:
                    if not code_file.exists():
                        with open(code_file, "w", encoding="utf-8") as cf:
                            cf.write(pre["code"])
                except Exception as ce:
                    logger.debug(f"Could not write preseeded skill code: {ce}")

                skills[sid] = {
                    "id": sid,
                    "name": pre["name"],
                    "description": pre["description"],
                    "trigger_phrases": pre["trigger_phrases"],
                    "keywords": pre["keywords"],
                    "code_file": str(code_file),
                    "code": pre["code"],
                    "success_count": pre.get("success_count", 1),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "last_used": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_builtin": True
                }
                updated = True

        if updated:
            self._save_skills(skills)

        return skills

    def _save_skills(self, skills: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """Persists the skills registry to disk."""
        target = skills if skills is not None else self.skills
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(target, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save skills index to {self.index_file}: {e}")

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extracts distinctive keywords from a command string."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = cleaned.split()
        return [t for t in tokens if len(t) > 2 and t not in _STOP_WORDS]

    @staticmethod
    def generate_slug(text: str) -> str:
        """Generates a clean filesystem slug from a trigger phrase."""
        clean = re.sub(r"[^\w\s-]", "", text.lower()).strip()
        slug = re.sub(r"[-\s]+", "_", clean)
        return slug[:40] if slug else f"skill_{int(time.time())}"

    def find_matching_skill(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Fuzzy matches user command against learned skills library.
        Returns the highest-confidence matching skill, or None if no match.
        """
        if not command or not self.skills:
            return None

        clean_cmd = re.sub(r"[^\w\s]", "", command.lower()).strip()
        cmd_keywords = set(self.extract_keywords(clean_cmd))

        best_skill = None
        best_score = 0.0

        for skill in self.skills.values():
            score = 0.0

            # 1. Exact phrase match with any trigger phrase
            for phrase in skill.get("trigger_phrases", []):
                clean_phrase = re.sub(r"[^\w\s]", "", phrase.lower()).strip()
                if clean_cmd == clean_phrase:
                    score = 1.0
                    break
                elif clean_phrase and (clean_phrase in clean_cmd or clean_cmd in clean_phrase):
                    score = max(score, 0.85)

            # 2. Keyword overlap match
            skill_keywords = set(skill.get("keywords", []))
            if skill_keywords and cmd_keywords:
                intersection = skill_keywords.intersection(cmd_keywords)
                keyword_score = len(intersection) / len(skill_keywords)
                if keyword_score >= 0.65:
                    score = max(score, 0.70 + (keyword_score * 0.25))

            if score > best_score:
                best_score = score
                best_skill = skill

        # Match threshold (>= 0.75 confidence)
        if best_score >= 0.75:
            logger.info(f"[SKILL MANAGER] Matched skill '{best_skill['name']}' (confidence: {best_score:.2f})")
            return best_skill

        return None

    def learn_skill(
        self,
        trigger_command: str,
        code: str,
        description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Learns and persists a working Python automation into the skill library.
        """
        if not trigger_command.strip() or not code.strip():
            return None

        # Ignore tiny trivial snippets (e.g. single print statements from tests)
        lines = [line.strip() for line in code.splitlines() if line.strip() and not line.strip().startswith("#")]
        if len(lines) <= 1 and any(lines[0].startswith(p) for p in ("print('ok')", 'print("ok")')):
            return None

        clean_trigger = trigger_command.strip().lower()
        slug = self.generate_slug(clean_trigger)
        keywords = self.extract_keywords(clean_trigger)

        # Check if skill already exists under this or similar slug
        existing = self.skills.get(slug)
        if existing:
            # Update existing skill code and trigger phrase
            if clean_trigger not in existing.get("trigger_phrases", []):
                existing.setdefault("trigger_phrases", []).append(clean_trigger)
            existing["code"] = code
            existing["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
            existing["success_count"] = existing.get("success_count", 0) + 1
            code_file = self.storage_dir / f"{slug}.py"
            try:
                with open(code_file, "w", encoding="utf-8") as cf:
                    cf.write(code)
            except Exception as e:
                logger.warning(f"Failed to update code file {code_file}: {e}")
            self._save_skills()
            return existing

        # Create new learned skill
        code_file = self.storage_dir / f"{slug}.py"
        try:
            with open(code_file, "w", encoding="utf-8") as cf:
                cf.write(code)
        except Exception as e:
            logger.warning(f"Failed to write code file {code_file}: {e}")

        name = trigger_command.strip().capitalize()
        if len(name) > 40:
            name = name[:37] + "..."

        skill_record = {
            "id": slug,
            "name": name,
            "description": description or f"Auto-learned automation for: '{trigger_command.strip()}'",
            "trigger_phrases": [clean_trigger],
            "keywords": keywords,
            "code_file": str(code_file),
            "code": code,
            "success_count": 1,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_builtin": False
        }

        self.skills[slug] = skill_record
        self._save_skills()
        logger.info(f"[SKILL MANAGER] Crystallized new learned skill: '{name}' ({slug})")
        return skill_record

    def record_execution(self, skill_id: str, success: bool, refined_code: Optional[str] = None) -> None:
        """
        Updates skill statistics and persists refined code if self-healing repaired it.
        """
        skill = self.skills.get(skill_id)
        if not skill:
            return

        skill["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")

        if success:
            skill["success_count"] = skill.get("success_count", 0) + 1
            if refined_code:
                skill["code"] = refined_code
                code_file = self.storage_dir / f"{skill_id}.py"
                try:
                    with open(code_file, "w", encoding="utf-8") as cf:
                        cf.write(refined_code)
                    logger.info(f"[SKILL MANAGER] Upgraded skill '{skill['name']}' with self-healed code.")
                except Exception as e:
                    logger.warning(f"Could not persist refined code: {e}")
        self._save_skills()

    def execute_skill(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a saved skill script directly in a subprocess.
        """
        code = skill.get("code", "")
        code_file = skill.get("code_file")

        if not code and code_file and os.path.exists(code_file):
            try:
                with open(code_file, "r", encoding="utf-8") as f:
                    code = f.read()
            except Exception as e:
                return {"success": False, "error": f"Could not read skill file: {e}"}

        if not code:
            return {"success": False, "error": "Skill contains no executable code."}

        proc = run_agent_code(code, timeout=30)
        success = (proc.returncode == 0)

        return {
            "success": success,
            "output": proc.stdout if success else proc.stderr,
            "error": proc.stderr if not success else ""
        }

    def delete_skill(self, skill_id: str) -> bool:
        """Deletes a skill from disk and registry."""
        if skill_id not in self.skills:
            return False

        code_file = self.storage_dir / f"{skill_id}.py"
        try:
            if code_file.exists():
                code_file.unlink()
        except Exception:
            pass

        del self.skills[skill_id]
        self._save_skills()
        logger.info(f"[SKILL MANAGER] Deleted skill: {skill_id}")
        return True

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns all skills sorted by success count and last used."""
        return sorted(
            list(self.skills.values()),
            key=lambda s: (s.get("success_count", 0), s.get("last_used", "")),
            reverse=True
        )


# Global singleton instance
skill_manager = SkillManager()

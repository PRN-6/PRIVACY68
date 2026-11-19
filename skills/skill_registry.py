"""
PRIVACY68 Markdown Skill Registry
Loads, indexes, and matches modular Markdown Agent Skills (SKILL.md).
Enables the Agent Brain to dynamically learn and execute tasks for any developer tool
or application without writing hardcoded Python wrapper classes.
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PRIVACY68.SkillRegistry")

# Common stop words to exclude when calculating query keywords
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "by", "with",
    "is", "it", "this", "that", "my", "me", "your", "please", "can", "you", "could",
    "would", "i", "want", "need", "just", "now", "do", "make", "get", "run", "start",
    "right", "here", "there", "also", "then", "so", "some", "any", "all", "up", "out"
})


class SkillRegistry:
    """Discovers and provides contextual prompt injection for SKILL.md files."""

    def __init__(self, root_skills_dir: Optional[str] = None):
        if root_skills_dir:
            self.root_skills_dir = Path(root_skills_dir).resolve()
        elif getattr(os.sys, "frozen", False):
            # In compiled PyInstaller bundle: check _MEIPASS, executable dir, and _internal
            exe_dir = Path(os.path.dirname(os.sys.executable))
            meipass = Path(getattr(os.sys, "_MEIPASS", ""))
            candidates = [meipass / "skills", exe_dir / "skills", exe_dir / "_internal" / "skills"]
            found = next((p for p in candidates if p.is_dir()), None)
            self.root_skills_dir = (found or exe_dir / "skills").resolve()
        else:
            self.root_skills_dir = Path(os.path.join(os.path.dirname(__file__), os.pardir, "skills")).resolve()
        
        # User appdata directory for custom developer skills
        appdata = os.environ.get("APPDATA") or str(Path.home())
        self.user_skills_dir = Path(appdata) / "PRIVACY68" / "skills"
        
        self._skills: Dict[str, Dict[str, Any]] = {}
        self.reload_skills()

    def reload_skills(self):
        """Scans both built-in and user custom skills directories for SKILL.md files."""
        self._skills.clear()

        # 1. Load built-in project skills
        self._scan_directory(self.root_skills_dir, is_builtin=True)

        # 2. Load user custom skills from %APPDATA%/PRIVACY68/skills/
        if self.user_skills_dir.exists():
            self._scan_directory(self.user_skills_dir, is_builtin=False)

        logger.info(f"[SKILL REGISTRY] Loaded {len(self._skills)} Markdown Skills: {list(self._skills.keys())}")

    def _scan_directory(self, base_dir: Path, is_builtin: bool = True):
        if not base_dir.exists():
            return

        for child in base_dir.iterdir():
            if child.is_dir():
                skill_file = child / "SKILL.md"
                if skill_file.is_file():
                    skill = self._parse_skill_file(skill_file, is_builtin=is_builtin)
                    if skill and skill.get("name"):
                        self._skills[skill["name"].lower()] = skill

    def _parse_skill_file(self, file_path: Path, is_builtin: bool) -> Optional[Dict[str, Any]]:
        """Parses a SKILL.md file with YAML frontmatter and Markdown body."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading skill file {file_path}: {e}")
            return None

        frontmatter: Dict[str, Any] = {}
        body = content

        # Check for YAML frontmatter between '---' markers
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if match:
            raw_yaml = match.group(1)
            body = match.group(2).strip()
            try:
                import yaml
                loaded = yaml.safe_load(raw_yaml)
                if isinstance(loaded, dict):
                    frontmatter = loaded
            except Exception:
                # Basic key-value fallback parser if yaml fails
                for line in raw_yaml.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        frontmatter[k.strip()] = v.strip().strip("'\"")

        name = frontmatter.get("name") or file_path.parent.name
        description = frontmatter.get("description", "")
        keywords = frontmatter.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        # Generate automatic keywords from name and description
        auto_words = set(re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", f"{name} {description}".lower()))

        # Extract CLI bins from OpenClaw and standard metadata
        metadata = frontmatter.get("metadata", {})
        if isinstance(metadata, dict):
            openclaw_meta = metadata.get("openclaw", {})
            if isinstance(openclaw_meta, dict):
                bins = openclaw_meta.get("requires", {}).get("bins", [])
                for b in bins:
                    auto_words.add(str(b).lower())
            req_bins = metadata.get("requires", {}).get("bins", [])
            if isinstance(req_bins, list):
                for b in req_bins:
                    auto_words.add(str(b).lower())

        # Extract keywords from Markdown headings (e.g., ## PRs, ## Issues, ## Async merges)
        headings = re.findall(r"^#+\s+(.+)$", body, re.MULTILINE)
        for h in headings:
            for w in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", h.lower()):
                auto_words.add(w)

        # Expand singular/plural variants so queries match regardless of grammatical number
        stems = set()
        for w in auto_words:
            if w.endswith("ies") and len(w) > 4:
                stems.add(w[:-3] + "y")
            elif w.endswith("es") and len(w) > 4:
                stems.add(w[:-2])
            elif w.endswith("s") and len(w) > 2:
                stems.add(w[:-1])
            elif not w.endswith("s"):
                stems.add(w + "s")
        auto_words |= stems

        # Expand explicit keywords and tokenize multi-word phrases
        kw_set = set()
        for k in keywords:
            k_lower = k.lower().strip()
            kw_set.add(k_lower)
            for part in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", k_lower):
                kw_set.add(part)

        combined_keywords = (kw_set | (auto_words - _STOP_WORDS))

        return {
            "name": name,
            "description": description,
            "keywords": sorted(list(combined_keywords)),
            "metadata": metadata,
            "body": body,
            "path": str(file_path),
            "is_builtin": is_builtin
        }

    def find_matching_skills(self, text: str, max_skills: int = 2) -> List[Dict[str, Any]]:
        """Finds matching skills based on text keywords and relevance score."""
        text_lower = text.lower()
        tokens = set(re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text_lower)) - _STOP_WORDS
        if not tokens:
            return []

        scored_skills = []
        for name, skill in self._skills.items():
            score = 0.0
            # Direct skill name match in query (e.g., "github", "docker", "vscode")
            if name in text_lower:
                score += 4.0

            # Direct CLI bin matches from metadata
            metadata = skill.get("metadata", {})
            bins = []
            if isinstance(metadata, dict):
                openclaw_meta = metadata.get("openclaw", {})
                if isinstance(openclaw_meta, dict):
                    bins.extend(openclaw_meta.get("requires", {}).get("bins", []))
                bins.extend(metadata.get("requires", {}).get("bins", []))
            for b in bins:
                if str(b).lower() in tokens:
                    score += 3.0

            # Keyword overlap
            skill_kws = set(skill.get("keywords", []))
            overlap = tokens & skill_kws
            score += len(overlap) * 1.5

            # Substring matching for phrases in keywords (e.g., "pull request")
            for kw in skill.get("keywords", []):
                if " " in kw and kw in text_lower:
                    score += 3.0

            if score >= 1.5:
                scored_skills.append((score, skill))

        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in scored_skills[:max_skills]]

    def build_skill_prompt_context(self, text: str) -> str:
        """Constructs active skill instruction prompt block for LLM code generation."""
        matches = self.find_matching_skills(text)
        if not matches:
            return ""

        context_blocks = []
        for skill in matches:
            body = skill.get("body", "").strip()
            # Allow full OpenClaw skills (up to 30,000 characters) without truncation
            if len(body) > 30000:
                body = body[:30000] + "\n...(remaining skill instructions truncated)..."
            
            context_blocks.append(
                f"### ACTIVE DEVELOPER SKILL GUIDELINES: {skill['name'].upper()}\n"
                f"Description: {skill.get('description', '')}\n"
                f"{body}"
            )

        return (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "DEVELOPER SKILL KNOWLEDGE (Follow these CLI and API patterns in your Python script):\n"
            + "\n\n".join(context_blocks) + "\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns metadata for all available skills."""
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "keywords": s["keywords"],
                "path": s["path"],
                "is_builtin": s["is_builtin"]
            }
            for s in self._skills.values()
        ]


# Singleton instance
skill_registry = SkillRegistry()


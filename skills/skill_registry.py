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
        self.root_skills_dir = Path(root_skills_dir or os.path.join(os.path.dirname(__file__), os.pardir, "skills")).resolve()
        
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
        combined_keywords = set(k.lower() for k in keywords) | (auto_words - _STOP_WORDS)

        return {
            "name": name,
            "description": description,
            "keywords": list(combined_keywords),
            "metadata": frontmatter.get("metadata", {}),
            "body": body,
            "path": str(file_path),
            "is_builtin": is_builtin
        }

    def find_matching_skills(self, text: str, max_skills: int = 2) -> List[Dict[str, Any]]:
        """Finds matching skills based on text keywords and relevance score."""
        tokens = set(re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())) - _STOP_WORDS
        if not tokens:
            return []

        scored_skills = []
        for name, skill in self._skills.items():
            score = 0.0
            # Direct name match in query
            if name in text.lower():
                score += 3.0

            # Keyword overlap
            skill_kws = set(skill.get("keywords", []))
            overlap = tokens & skill_kws
            score += len(overlap) * 1.5

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
            # Truncate very long skill documents to avoid token blowout
            if len(body) > 3000:
                body = body[:3000] + "\n...(remaining skill instructions truncated)..."
            
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


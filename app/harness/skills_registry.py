import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


class JITSkillRegistry:
    """
    Just-In-Time (JIT) Skill Registry.
    Indexes skills cleanly and provides lightweight summary catalogs
    and on-demand skill reading tools for self-contained agents.
    """

    @staticmethod
    def _parse_skill_metadata(file_path: Path) -> Dict[str, str]:
        """Parses frontmatter metadata (name, description) from a SKILL.md file."""
        skill_name = file_path.parent.name if file_path.stem.lower() == "skill" else file_path.stem
        description = "Specialized domain instructions."
        try:
            content = file_path.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    if isinstance(meta, dict):
                        skill_name = str(meta.get("name", skill_name)).strip()
                        description = str(meta.get("description", description)).strip()
        except Exception as e:
            logger.debug(f"Could not parse frontmatter for {file_path}: {e}")

        return {
            "name": skill_name,
            "description": description,
            "file_path": str(file_path.resolve()),
        }

    @classmethod
    def get_skills_catalog(cls, skills_dir: Path) -> str:
        """
        Returns a compact Markdown summary table of available skills
        for lightweight prompt injection without token bloat.
        """
        if not skills_dir.exists() or not skills_dir.is_dir():
            return "No local skills registered."

        rows = ["| Skill Name | Description |", "|---|---|"]
        found = False
        for file_path in sorted(skills_dir.rglob("*.md")):
            meta = cls._parse_skill_metadata(file_path)
            # Escape pipes in description
            clean_desc = meta["description"].replace("\n", " ").replace("|", "/")
            rows.append(f"| `{meta['name']}` | {clean_desc[:120]} |")
            found = True

        if not found:
            return "No local skills registered."
        return "\n".join(rows)

    @staticmethod
    def search_skills(query: str, skills_dir: Optional[Path] = None) -> List[Dict[str, str]]:
        """
        Searches available skills by keyword or domain phrase.
        Returns matching skill metadata (`name` and `description`).
        """
        results = []
        search_dirs = []
        if skills_dir and skills_dir.exists():
            search_dirs.append(skills_dir)

        query_tokens = [t.lower() for t in re.findall(r"[a-z0-9]+", query) if len(t) >= 3]
        for s_dir in search_dirs:
            for file_path in sorted(s_dir.rglob("*.md")):
                meta = JITSkillRegistry._parse_skill_metadata(file_path)
                combined = f"{meta['name']} {meta['description']}".lower()
                if query.lower() in combined or any(tok in combined for tok in query_tokens):
                    results.append({
                        "name": meta["name"],
                        "description": meta["description"],
                    })
        return results

    @staticmethod
    def read_skill(skill_name: str, skills_dir: Optional[Path] = None) -> str:
        """
        Reads and returns the complete markdown instructions for a specific skill.
        Should be called by agents via tool invocation when specialized guidance is needed.
        """
        search_dirs = []
        if skills_dir and skills_dir.exists():
            search_dirs.append(skills_dir)

        clean_target = skill_name.strip().lower()
        for s_dir in search_dirs:
            for file_path in sorted(s_dir.rglob("*.md")):
                meta = JITSkillRegistry._parse_skill_metadata(file_path)
                if meta["name"].lower() == clean_target or file_path.parent.name.lower() == clean_target:
                    try:
                        return file_path.read_text(encoding="utf-8")
                    except Exception as e:
                        return f"Error reading skill file '{file_path}': {e}"

        return f"Skill '{skill_name}' not found. Check available skills using `search_skills` or view your prompt catalog."

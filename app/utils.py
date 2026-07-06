import os
import shutil
from pathlib import Path
import json
from typing import Any

def parse_node_input(node_input: Any) -> Any:
    """Safely extracts and parses node input from ADK Content/Part objects or strings into dictionaries or strings."""
    if hasattr(node_input, "parts") and getattr(node_input, "parts", None):
        for p in node_input.parts:
            if getattr(p, "text", None):
                node_input = p.text
                break
    if isinstance(node_input, str):
        try:
            parsed = json.loads(node_input)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return node_input

class FilesystemJail:
    """Utility class to enforce strictly jailed filesystem sandboxing on a per-project basis.
    All file operations are contained within the `outputs/[project_id]/` subdirectory.
    """
    
    BASE_OUTPUT_DIR = Path("C:/Users/Fred/Documents/antigravity/blueprint-engine/outputs").resolve()

    @classmethod
    def get_project_dir(cls, project_id: str) -> Path:
        """Resolves and returns the absolute Path of the project's output folder,
        ensuring it is created. Enforces that the project_id cannot exploit path traversal.
        """
        # Sanitize project_id to prevent any sneaky path injection
        sanitized_id = Path(project_id).name
        project_dir = (cls.BASE_OUTPUT_DIR / sanitized_id).resolve()
        
        # Double check containment
        if not project_dir.is_relative_to(cls.BASE_OUTPUT_DIR):
            raise PermissionError(f"Security Violation: Project directory '{project_dir}' escapes jail perimeter.")
            
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    @classmethod
    def resolve_jailed_path(cls, project_id: str, relative_filename: str) -> Path:
        """Safely resolves a relative filename inside a project's jailed directory.
        Raises PermissionError if the resolved path attempts to escape the jail.
        """
        project_dir = cls.get_project_dir(project_id)
        target_path = (project_dir / relative_filename).resolve()
        
        # Verify target path is strictly contained within the project directory
        if not target_path.is_relative_to(project_dir):
            raise PermissionError(
                f"Security Violation: Target path '{target_path}' attempts to traverse outside of the project "
                f"jail folder '{project_dir}'."
            )
            
        return target_path

    @classmethod
    def write_project_file(cls, project_id: str, relative_filename: str, content: str) -> Path:
        """Securely writes content to a file inside the project's sandboxed directory."""
        safe_path = cls.resolve_jailed_path(project_id, relative_filename)
        safe_path.write_text(content, encoding="utf-8")
        return safe_path

    @classmethod
    def read_project_file(cls, project_id: str, relative_filename: str) -> str:
        """Securely reads content from a file inside the project's sandboxed directory."""
        safe_path = cls.resolve_jailed_path(project_id, relative_filename)
        if not safe_path.exists():
            raise FileNotFoundError(f"File '{relative_filename}' does not exist inside project jail.")
        return safe_path.read_text(encoding="utf-8")

    @classmethod
    def delete_project_dir(cls, project_id: str) -> None:
        """Securely deletes a project's entire directory."""
        project_dir = cls.get_project_dir(project_id)
        if project_dir.exists() and project_dir.is_dir():
            shutil.rmtree(project_dir)

def load_matching_skills(skills_dir: Path, text_to_match: str) -> str:
    """Scans a skills directory for Markdown files, matches YAML frontmatter metadata

    against the provided text, and returns a formatted string of matching skills.
    Adheres to JIT skill injection without polluting global context.
    """
    if not skills_dir.exists() or not skills_dir.is_dir() or not text_to_match:
        return ""

    import re
    matched_skills = []
    text_lower = text_to_match.lower()
    
    # Common stop words to ignore during token matching
    stop_words = {
        "and", "for", "the", "with", "from", "this", "that", "use", "when", "how",
        "are", "can", "will", "best", "practices", "patterns", "design", "guide",
        "about", "into", "over", "under", "where", "what", "which", "while", "skill"
    }

    for file_path in sorted(skills_dir.rglob("*.md")):
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract YAML frontmatter if present using PyYAML
        frontmatter_text = ""
        skill_name = file_path.parent.name if file_path.stem.lower() == "skill" else file_path.stem
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    meta = yaml.safe_load(parts[1]) or {}
                    if isinstance(meta, dict):
                        skill_name = str(meta.get("name", skill_name)).strip()
                        frontmatter_text = f"{skill_name} {meta.get('description', '')} {meta.get('keywords', '')}".lower()
                except Exception:
                    frontmatter_text = parts[1].lower()
        else:
            frontmatter_text = content[:500].lower() # fallback to first 500 chars

        # Extract meaningful tokens from skill name and frontmatter description
        raw_tokens = re.findall(r'[a-z0-9]+', f"{skill_name} {frontmatter_text}")
        tokens = {t for t in raw_tokens if len(t) >= 3 and t not in stop_words}

        # Check if skill name phrase or any significant token appears in text_to_match
        name_phrase = skill_name.lower().replace("-", " ").replace("_", " ")
        is_match = name_phrase in text_lower or any(
            re.search(r'\b' + re.escape(token) + r'\b', text_lower) for token in tokens
        )

        if is_match:
            matched_skills.append(f"\n--- SKILL: {skill_name} ---\n{content.strip()}\n")

    return "\n".join(matched_skills)


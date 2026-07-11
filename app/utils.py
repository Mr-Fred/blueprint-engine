import os
import shutil
from pathlib import Path
import json
from typing import Any, Optional

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
        safe_path.parent.mkdir(parents=True, exist_ok=True)
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

def load_matching_skills(skills_dir: Path, text_to_match: str = "") -> str:
    """
    Scans a skills directory for Markdown files and matches YAML frontmatter metadata
    against the provided text. Adheres to JIT skill injection without polluting global context.
    """
    if not skills_dir.exists() or not skills_dir.is_dir() or not text_to_match:
        return ""

    import re
    from app.harness.skills_registry import JITSkillRegistry

    matched_skills = []
    text_lower = text_to_match.lower()
    stop_words = {
        "and", "for", "the", "with", "from", "this", "that", "use", "when", "how",
        "are", "can", "will", "best", "practices", "patterns", "design", "guide",
        "about", "into", "over", "under", "where", "what", "which", "while", "skill",
        "need", "implement", "let", "our", "must",
    }

    for file_path in sorted(skills_dir.rglob("*.md")):
        meta = JITSkillRegistry._parse_skill_metadata(file_path)
        skill_name = meta["name"]
        frontmatter_text = f"{skill_name} {meta['description']}".lower()

        raw_tokens = re.findall(r'[a-z0-9]+', frontmatter_text)
        tokens = {t for t in raw_tokens if len(t) >= 3 and t not in stop_words}

        name_phrase = skill_name.lower().replace("-", " ").replace("_", " ")
        is_match = name_phrase in text_lower or any(
            re.search(r'\b' + re.escape(token) + r'\b', text_lower) for token in tokens
        )

        if is_match:
            try:
                content = file_path.read_text(encoding="utf-8")
                matched_skills.append(f"\n--- SKILL: {skill_name} ---\n{content.strip()}\n")
            except Exception:
                continue

    return "\n".join(matched_skills)


def extract_stream_chunk_text(chunk: Any) -> str:
    """Extracts text content cleanly from streamed interaction SSE chunks or standard generate_content_stream chunks."""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        if chunk.get("text"):
            return str(chunk["text"])
        delta = chunk.get("delta")
        if isinstance(delta, dict) and delta.get("text"):
            return str(delta["text"])

    text = getattr(chunk, "text", None)
    if text and isinstance(text, str):
        return text

    delta = getattr(chunk, "delta", None)
    if delta:
        d_text = getattr(delta, "text", None)
        if d_text:
            return str(d_text)
        d_content = getattr(delta, "content", None)
        if d_content and hasattr(d_content, "parts") and d_content.parts:
            for p in d_content.parts:
                p_text = getattr(p, "text", None)
                if p_text:
                    return str(p_text)

    candidates = getattr(chunk, "candidates", None)
    if candidates and len(candidates) > 0:
        c_content = getattr(candidates[0], "content", None)
        if c_content and getattr(c_content, "parts", None):
            for p in c_content.parts:
                p_text = getattr(p, "text", None)
                if p_text:
                    return str(p_text)

    steps = getattr(chunk, "steps", None)
    if steps and len(steps) > 0:
        step = steps[-1]
        content = getattr(step, "content", None)
        if content and len(content) > 0:
            part = content[0]
            if hasattr(part, "text") and part.text:
                return str(part.text)

    return ""


def extract_interaction_id(chunk: Any) -> Optional[str]:
    """Extracts server-side interaction ID from completed interaction SSE events or chunks."""
    chunk_id = getattr(chunk, "id", None)
    if chunk_id:
        return chunk_id
    interaction = getattr(chunk, "interaction", None)
    if interaction and getattr(interaction, "id", None):
        return interaction.id
    return None




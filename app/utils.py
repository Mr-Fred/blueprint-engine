import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)



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

    write_file = write_project_file


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
    all_skills = []
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
            desc = meta.get("description", "").strip()
            matched_skills.append(f"- **{skill_name}**: {desc} (Invoke tool `read_skill(\"{skill_name}\")` to inspect full markdown instructions)")
        all_skills.append(f"- **{skill_name}**: {meta.get('description', '').strip()} (Invoke tool `read_skill(\"{skill_name}\")`)")

    skills_to_show = matched_skills if matched_skills else all_skills
    if not skills_to_show:
        return ""

    header = (
        "Available Domain Skills & Tool Calling Mandate:\n"
        "CRITICAL INSTRUCTION: Before finalizing your architectural response, you MUST use your tool-calling capabilities:\n"
        "1. Call `read_skill(skill_name)` to load detailed instructions for relevant skills listed below.\n"
        "2. Call `lookup_architectural_pattern(pattern_name)` or `check_owasp_stride_vector(component_type)` as needed.\n\n"
        "Available Skills:\n"
    )
    return header + "\n".join(skills_to_show)


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
        finish_reason = getattr(candidates[0], "finish_reason", None)
        if finish_reason is not None:
            fr_str = str(finish_reason).upper()
            if any(bad in fr_str for bad in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT")):
                logger.error(f"[MODEL STREAM INTERRUPTED] Stream chunk terminated with finish_reason: {finish_reason}")
                raise RuntimeError(f"Stream interrupted by model safety/recitation guard: {finish_reason}")

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

def truncate_prompt_text(text: str, max_chars: int = 4500) -> str:
    """
    Deprecated: Truncates large prompt strings or historical drafts.
    Preserves both head and tail context.
    """
    if not text or not isinstance(text, str):
        return ""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return (
        text[:half].rstrip()
        + "\n\n... [TRUNCATED FOR CONTEXT WINDOW EFFICIENCY] ...\n\n"
        + text[-half:].lstrip()
    )


def extract_interaction_id(chunk: Any) -> str | None:
    """Extracts server-side interaction ID from completed interaction SSE events or chunks."""
    chunk_id = getattr(chunk, "id", None)
    if chunk_id:
        return chunk_id
    interaction = getattr(chunk, "interaction", None)
    if interaction and getattr(interaction, "id", None):
        return interaction.id
    return None


async def call_with_retry_on_429(coro_factory, max_retries: int = 3, base_delay: float = 3.0):
    """
    Executes an async function factory with exponential backoff retries when encountering
    rate limit (429 / RESOURCE_EXHAUSTED) exceptions.
    Starts backoff delay at `base_delay` (default 3.0s).
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            err_str = str(e).upper()
            is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "TOO MANY REQUESTS" in err_str
            if is_429 and attempt < max_retries:
                logger.warning(
                    f"Rate limit (429 RESOURCE_EXHAUSTED) encountered. Attempt {attempt}/{max_retries}. "
                    f"Retrying in {delay} seconds..."
                )
                await asyncio.sleep(delay)
                delay *= 2.0
            else:
                raise


def log_gemini_inspection(call_type: str, model_id: str, response_obj: Any, extra: dict | None = None) -> None:
    """
    Logs Gemini API response objects (interactions.create, generate_content_stream, generate_content)
    to a dedicated file 'logs/gemini_inspection.jsonl' for clean debugging without terminal noise.
    """
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gemini_inspection.jsonl"

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_type": call_type,
        "model_id": model_id,
    }

    if extra:
        entry["extra"] = extra

    # Extract common fields safely
    candidates = getattr(response_obj, "candidates", None)
    if candidates and len(candidates) > 0:
        c = candidates[0]
        entry["finish_reason"] = str(getattr(c, "finish_reason", "UNKNOWN"))
        entry["safety_ratings"] = str(getattr(c, "safety_ratings", None))
    else:
        entry["finish_reason"] = "NO_CANDIDATES"

    text = getattr(response_obj, "text", None)
    entry["text_len"] = len(text) if text else 0
    fcs = getattr(response_obj, "function_calls", None)
    entry["function_calls"] = [getattr(fc, "name", str(fc)) for fc in fcs] if fcs else []
    entry["raw_repr"] = repr(response_obj)[:1500]

    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def extract_token_usage_dict(response_obj: Any) -> dict[str, int]:
    """Safely extracts prompt, completion, and total token usage counts from a Gemini response object."""
    usage = getattr(response_obj, "usage_metadata", None)
    if not usage:
        return {}
    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = getattr(usage, "total_token_count", 0) or (int(prompt_tokens) + int(completion_tokens))
    return {
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(total_tokens),
    }




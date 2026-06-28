import os
import shutil
from pathlib import Path

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

import pytest
from pathlib import Path
from app.utils import FilesystemJail

def test_filesystem_jail_valid_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that normal, non-malicious write and read operations are allowed and successful."""
    # Temporarily point BASE_OUTPUT_DIR to our clean temp dir
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path.resolve())
    
    project_id = "test_project_123"
    filename = "spec.md"
    content = "# Software Specification"
    
    # Write file safely
    written_path = FilesystemJail.write_project_file(project_id, filename, content)
    assert written_path.exists()
    assert written_path.name == filename
    
    # Read file safely
    read_content = FilesystemJail.read_project_file(project_id, filename)
    assert read_content == content

def test_filesystem_jail_traversal_prevention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that attempting to read/write outside the project jail directory is blocked."""
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path.resolve())
    
    project_id = "secured_project"
    
    # Attempting to write escaping the project folder using relative parent traversal
    dangerous_filename = "../escaped_secret.txt"
    
    with pytest.raises(PermissionError) as exc_info:
        FilesystemJail.write_project_file(project_id, dangerous_filename, "sensitive data")
        
    assert "escapes jail" in str(exc_info.value) or "attempts to traverse" in str(exc_info.value)

def test_filesystem_jail_project_id_traversal_prevention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that project_id itself cannot contain directory traversal characters."""
    monkeypatch.setattr(FilesystemJail, "BASE_OUTPUT_DIR", tmp_path.resolve())
    
    dangerous_project_id = "../../malicious_project"
    
    # Since get_project_dir uses Path(project_id).name, it should resolve to 'malicious_project'
    # under BASE_OUTPUT_DIR, thereby remaining fully jailed.
    resolved_dir = FilesystemJail.get_project_dir(dangerous_project_id)
    assert resolved_dir.is_relative_to(tmp_path)
    assert resolved_dir.name == "malicious_project"

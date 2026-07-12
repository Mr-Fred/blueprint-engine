from pathlib import Path
from app.utils import load_matching_skills

def test_load_matching_skills(tmp_path: Path):
    """Tests the load_matching_skills utility function for YAML frontmatter matching

    and JIT prompt formatting using a temporary directory fixture.
    """
    # 1. Test empty or non-existent directory
    assert load_matching_skills(tmp_path / "nonexistent", "some text") == ""
    assert load_matching_skills(tmp_path, "") == ""

    # 2. Create mock skill files with YAML frontmatter
    auth_skill = tmp_path / "auth-patterns.md"
    auth_skill.write_text(
        "---\n"
        "name: auth-patterns\n"
        "description: Master authentication and authorization patterns including JWT, OAuth2, and RBAC.\n"
        "---\n\n"
        "# Auth Patterns\n"
        "Always use short-lived JWTs and secure HTTP-only cookies.",
        encoding="utf-8"
    )

    db_skill = tmp_path / "db-design.md"
    db_skill.write_text(
        "---\n"
        "name: db-design\n"
        "description: PostgreSQL schema design, indexing strategies, and normalization.\n"
        "---\n\n"
        "# DB Design\n"
        "Always index foreign keys and use B-tree indexes for range queries.",
        encoding="utf-8"
    )

    # 3. Test matching on auth tokens
    auth_result = load_matching_skills(tmp_path, "We need to implement secure JWT and OAuth2 authentication.")
    assert "- **auth-patterns**:" in auth_result
    assert 'read_skill("auth-patterns")' in auth_result
    assert "db-design" not in auth_result

    # 4. Test matching on DB tokens
    db_result = load_matching_skills(tmp_path, "Let's optimize our PostgreSQL indexing strategies.")
    assert "- **db-design**:" in db_result
    assert 'read_skill("db-design")' in db_result
    assert "auth-patterns" not in db_result

    # 5. Test real agent skills directory matching
    security_skills_dir = Path("app/agents/security/skills").resolve()
    if security_skills_dir.exists():
        real_result = load_matching_skills(
            security_skills_dir,
            "We must translate threats into actionable security requirements and user stories."
        )
        assert "security-requirement-extraction" in real_result

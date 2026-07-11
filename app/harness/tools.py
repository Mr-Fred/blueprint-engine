import logging
from typing import Any, Dict, List
from app.harness.sandbox import LeadArchitectWorkspace, SecurityAuditorWorkspace
from app.harness.ledger import EpistemicScratchpad

logger = logging.getLogger(__name__)


class HarnessToolRegistry:
    """
    Deterministic Harness Tool Registry.
    Provides read-only query tools and epistemic fact registration tools
    that self-contained agents can invoke on-demand via GenAI tool calling.
    """

    @staticmethod
    def lookup_architectural_pattern(pattern_name: str) -> str:
        """Looks up an architectural pattern definition and cloud reference components."""
        catalog = LeadArchitectWorkspace.get_pattern_catalog()
        clean_key = pattern_name.strip().lower().replace(" ", "_")
        desc = catalog.get(clean_key)
        if not desc:
            # Try fuzzy matching substring
            for k, val in catalog.items():
                if clean_key in k or k in clean_key:
                    clean_key = k
                    desc = val
                    break

        if not desc:
            available = ", ".join(catalog.keys())
            return f"Pattern '{pattern_name}' not found. Available patterns: {available}"

        cloud_refs = LeadArchitectWorkspace.get_cloud_reference(clean_key)
        ref_str = ", ".join(cloud_refs) if cloud_refs else "No specific cloud topology registered."
        return f"Pattern: {clean_key}\nDescription: {desc}\nRecommended Cloud Components: {ref_str}"

    @staticmethod
    def check_owasp_stride_vector(vector_name: str) -> str:
        """Looks up an OWASP STRIDE threat vector description and mitigation guidance."""
        vectors = SecurityAuditorWorkspace.get_owasp_threat_vectors()
        clean_key = vector_name.strip().replace(" ", "_")
        desc = vectors.get(clean_key)
        if not desc:
            for k, val in vectors.items():
                if clean_key.lower() in k.lower():
                    clean_key = k
                    desc = val
                    break

        if not desc:
            available = ", ".join(vectors.keys())
            return f"STRIDE vector '{vector_name}' not found. Available vectors: {available}"

        return f"STRIDE Vector: {clean_key}\nRisk Description: {desc}"

    @staticmethod
    def check_compliance_checklist(framework: str) -> List[str]:
        """Returns the compliance checklist items for a specified standard (e.g., 'soc2', 'gdpr', 'hipaa')."""
        checklist = SecurityAuditorWorkspace.get_compliance_checklist(framework)
        if not checklist:
            return [f"No checklist registered for compliance framework '{framework}'. Supported: soc2, gdpr, hipaa"]
        return checklist

    @staticmethod
    def query_verified_facts(project_id: str) -> List[Dict[str, Any]]:
        """Queries all mutually verified epistemic facts currently locked in the Epistemic Scratchpad."""
        scratchpad = EpistemicScratchpad.load(project_id)
        return [fact.model_dump() for fact in scratchpad.verified_facts]

    @staticmethod
    def add_verified_fact(project_id: str, statement: str, verifier: str = "LeadArchitect") -> Dict[str, Any]:
        """Registers a newly verified architectural fact into the Epistemic Scratchpad."""
        scratchpad = EpistemicScratchpad.load(project_id)
        event = scratchpad.add_fact(statement=statement, verifier=verifier)
        return event.model_dump()

    @staticmethod
    def write_synthesized_artifact(project_id: str, relative_path: str, content: str) -> str:
        """
        Validates and securely writes a synthesized production artifact to the sandboxed output directory
        (e.g., ARCHITECTURE.md, docs/prd.md, diagrams/topology.mmd, security/risk_matrix.json).
        Executes fail-safe programmatic syntax validation before writing to disk.
        """
        from app.harness.sensors import ArtifactSyntaxValidator
        from app.utils import FilesystemJail

        validation_errors = ArtifactSyntaxValidator.validate_artifact(relative_path, content)
        if validation_errors:
            err_msg = "; ".join(validation_errors)
            return f"VALIDATION_ERROR: Cannot write '{relative_path}': {err_msg}"

        safe_path = FilesystemJail.write_project_file(project_id, relative_path, content)
        return f"SUCCESS: Wrote '{relative_path}' ({len(content)} bytes) to sandboxed workspace '{safe_path}'."


def format_tools_for_interactions(functions: list) -> list[dict]:
    """Formats Python function callables into standard Tool dictionaries required by client.aio.interactions.create."""
    tools = []
    for fn in functions:
        name = getattr(fn, "__name__", str(fn))
        doc = getattr(fn, "__doc__", "") or f"Tool {name}"
        tools.append({
            "type": "function",
            "name": name,
            "description": doc.strip()
        })
    return tools


def lookup_architectural_pattern(pattern_name: str) -> str:
    """Looks up an architectural pattern definition and cloud reference components."""
    return HarnessToolRegistry.lookup_architectural_pattern(pattern_name)


def query_verified_facts(project_id: str) -> List[Dict[str, Any]]:
    """Queries all mutually verified epistemic facts currently locked in the Epistemic Scratchpad."""
    return HarnessToolRegistry.query_verified_facts(project_id)


def add_verified_fact(project_id: str, statement: str, verifier: str = "LeadArchitect") -> Dict[str, Any]:
    """Registers a newly verified architectural fact into the Epistemic Scratchpad."""
    return HarnessToolRegistry.add_verified_fact(project_id, statement, verifier)


def check_owasp_stride_vector(vector_name: str) -> str:
    """Looks up an OWASP STRIDE threat vector description and mitigation guidance."""
    return HarnessToolRegistry.check_owasp_stride_vector(vector_name)


def check_compliance_checklist(framework: str) -> List[str]:
    """Returns the compliance checklist items for a specified standard (e.g., 'soc2', 'gdpr', 'hipaa')."""
    return HarnessToolRegistry.check_compliance_checklist(framework)


def write_synthesized_artifact(project_id: str, relative_path: str, content: str) -> str:
    """Validates and securely writes a synthesized production artifact to the sandboxed output directory."""
    return HarnessToolRegistry.write_synthesized_artifact(project_id, relative_path, content)


def read_skill(skill_name: str) -> str:
    """Reads the full instructions of a specific skill by name."""
    from app.harness.skills_registry import JITSkillRegistry
    return JITSkillRegistry.read_skill(skill_name=skill_name)


def search_skills(query: str) -> str:
    """Searches available skills by keyword or domain phrase."""
    from app.harness.skills_registry import JITSkillRegistry
    results = JITSkillRegistry.search_skills(query=query)
    return str(results)


def get_harness_tools() -> list:
    """Returns clean standalone Python functions wrapping HarnessToolRegistry and JITSkillRegistry."""
    from app.harness.skills_registry import JITSkillRegistry
    return [
        lookup_architectural_pattern,
        check_owasp_stride_vector,
        check_compliance_checklist,
        query_verified_facts,
        add_verified_fact,
        write_synthesized_artifact,
        read_skill,
        search_skills,
    ]




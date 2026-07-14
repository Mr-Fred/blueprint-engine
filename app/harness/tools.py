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


recent_tool_executions: List[Dict[str, Any]] = []

def record_tool_execution(tool_name: str, args: Dict[str, Any], result_preview: str) -> None:
    recent_tool_executions.append({
        "tool_name": tool_name,
        "args": args,
        "result_preview": result_preview,
    })


async def generate_content_with_tools(
    client: Any,
    model_id: str,
    prompt: str,
    tools: list,
    max_tool_turns: int = 5,
    system_instruction: str = None,
) -> str:
    """
    Executes a multi-turn non-streaming tool-calling loop against Gemini.
    When Gemini emits function_calls, executes the tools locally against HarnessToolRegistry
    and feeds function_response back into the conversation until Gemini outputs Markdown text.
    """
    from google.genai import types

    from app.utils import call_with_retry_on_429, log_gemini_inspection

    tool_map = {f.__name__: f for f in tools}
    contents = [prompt]
    final_text = ""

    for turn in range(max_tool_turns):
        config_kwargs = {"tools": tools}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if turn == 0 and tools:
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )

        config = types.GenerateContentConfig(**config_kwargs)
        res = await call_with_retry_on_429(
            lambda: client.aio.models.generate_content(
                model=model_id,
                contents=contents,
                config=config,
            ),
            max_retries=3,
            base_delay=3.0,
        )
        log_gemini_inspection("generate_content_with_tools", model_id, res, {"turn": turn})

        fcs = getattr(res, "function_calls", None)
        if not fcs or turn == max_tool_turns - 1:
            if getattr(res, "text", None):
                final_text = res.text
            break

        if getattr(res, "candidates", None) and res.candidates[0].content:
            contents.append(res.candidates[0].content)

        tool_parts = []
        for fc in fcs:
            fc_name = getattr(fc, "name", None)
            fc_args = dict(getattr(fc, "args", {}))
            func = tool_map.get(fc_name)
            if func:
                try:
                    tool_res = func(**fc_args)
                except Exception as e:
                    tool_res = f"Error executing tool {fc_name}: {str(e)}"
            else:
                tool_res = f"Tool {fc_name} not found."

            logger.info(f"Executed harness tool {fc_name}({fc_args}) -> {str(tool_res)[:100]}")
            record_tool_execution(fc_name, fc_args, str(tool_res)[:120])
            tool_parts.append(
                types.Part.from_function_response(name=fc_name, response={"result": tool_res})
            )

        if tool_parts:
            contents.append(types.Content(role="tool", parts=tool_parts))

    return final_text


async def stream_agent_with_tools(
    client: Any,
    model_id: str,
    prompt: str,
    tools: list,
    max_tool_turns: int = 5,
    response_schema: Any = None,
):
    """
    Executes a multi-turn streaming tool-calling loop against Gemini.
    When Gemini emits function_call chunks, executes the tools locally against HarnessToolRegistry
    and feeds function_response back into the conversation until Gemini streams Markdown text.
    Yields each text chunk as it arrives.
    """
    from google.genai import types

    from app.utils import extract_stream_chunk_text

    tool_map = {f.__name__: f for f in tools}
    contents = [prompt]

    for turn in range(max_tool_turns):
        config_kwargs = {"tools": tools} if turn < max_tool_turns - 1 else {}
        if turn == 0 and tools:
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        from app.utils import call_with_retry_on_429
        response_stream = await call_with_retry_on_429(
            lambda: client.aio.models.generate_content_stream(
                model=model_id,
                contents=contents,
                config=config,
            ),
            max_retries=3,
            base_delay=3.0,
        )

        turn_model_parts = []
        turn_function_calls = []
        turn_texts = []
        from app.utils import log_gemini_inspection
        async for chunk in response_stream:
            log_gemini_inspection("generate_content_stream_chunk", model_id, chunk, {"turn": turn})
            text = extract_stream_chunk_text(chunk)
            if text:
                turn_texts.append(text)

            candidates = getattr(chunk, "candidates", None)
            if candidates:
                for c in candidates:
                    content = getattr(c, "content", None)
                    parts = getattr(content, "parts", None) if content else None
                    if parts:
                        for p in parts:
                            turn_model_parts.append(p)
                            fc = getattr(p, "function_call", None)
                            if fc and getattr(fc, "name", None):
                                turn_function_calls.append((fc.name, dict(getattr(fc, "args", {}))))

        if not turn_function_calls or turn == max_tool_turns - 1:
            if response_schema:
                schema_config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                )
                structured_res = await call_with_retry_on_429(
                    lambda: client.aio.models.generate_content(
                        model=model_id,
                        contents=contents,
                        config=schema_config,
                    ),
                    max_retries=3,
                    base_delay=3.0,
                )
                if getattr(structured_res, "text", None):
                    yield structured_res.text
            else:
                for t in turn_texts:
                    yield t
            break

        if turn_model_parts:
            contents.append(types.Content(role="model", parts=turn_model_parts))

        tool_parts = []
        for fc_name, fc_args in turn_function_calls:
            func = tool_map.get(fc_name)
            if func:
                try:
                    res = func(**fc_args)
                except Exception as e:
                    res = f"Error executing tool {fc_name}: {str(e)}"
            else:
                res = f"Tool {fc_name} not found."

            logger.info(f"Executed harness tool {fc_name}({fc_args}) -> {str(res)[:100]}")
            record_tool_execution(fc_name, fc_args, str(res)[:120])
            tool_parts.append(
                types.Part.from_function_response(name=fc_name, response={"result": res})
            )

        if tool_parts:
            contents.append(types.Content(role="tool", parts=tool_parts))




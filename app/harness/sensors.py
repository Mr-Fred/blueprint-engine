import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.types import DebateRoundEnvelope, PillarScores
from app.harness.ledger import EpistemicScratchpad

logger = logging.getLogger(__name__)


class SensorResult(BaseModel):
    """Result of running Left-Shifted Blueprint Sensors across a proposed round artifact."""
    passed: bool = Field(..., description="True if all computational sensors passed")
    failed_layer: Optional[str] = Field(None, description="Name of the first sensor layer that failed")
    errors: List[str] = Field(default_factory=list, description="List of specific validation errors")
    formatted_backpressure: Optional[str] = Field(
        None, description="Formatted prompt payload to send back to the agent for self-correction"
    )


class DiagramSyntaxSensor:
    """
    Pure-Python structural Mermaid diagram syntax validator.
    Extracts embedded ```mermaid blocks and validates structural headers and balanced brackets.
    """
    VALID_HEADERS = (
        "graph ",
        "flowchart ",
        "sequencediagram",
        "classdiagram",
        "statediagram",
        "erdiagram",
        "gantt",
        "pie",
        "mindmap",
    )

    @classmethod
    def validate_diagrams(cls, markdown_text: str) -> List[str]:
        """Scans markdown for ```mermaid blocks and returns a list of structural syntax errors."""
        errors: List[str] = []
        blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", markdown_text, re.DOTALL | re.IGNORECASE)

        for idx, block in enumerate(blocks, start=1):
            lines = [line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("%%")]
            if not lines:
                errors.append(f"Mermaid block #{idx} is empty.")
                continue

            first_line = lines[0].lower()
            if not any(first_line.startswith(hdr) for hdr in cls.VALID_HEADERS):
                errors.append(
                    f"Mermaid block #{idx} invalid header line: '{lines[0]}'. Must start with a valid diagram type (e.g., 'graph TD', 'sequenceDiagram')."
                )

            # Validate bracket balance across diagram lines
            for l_idx, line in enumerate(lines, start=1):
                open_sq = line.count("[")
                close_sq = line.count("]")
                if open_sq != close_sq:
                    errors.append(
                        f"Mermaid block #{idx} line {l_idx}: Mismatched square brackets '[' ({open_sq}) vs ']' ({close_sq}) in '{line}'"
                    )

                open_paren = line.count("(")
                close_paren = line.count(")")
                if open_paren != close_paren:
                    errors.append(
                        f"Mermaid block #{idx} line {l_idx}: Mismatched parentheses '(' ({open_paren}) vs ')' ({close_paren}) in '{line}'"
                    )

                open_brace = line.count("{")
                close_brace = line.count("}")
                if open_brace != close_brace:
                    errors.append(
                        f"Mermaid block #{idx} line {l_idx}: Mismatched curly braces '{{' ({open_brace}) vs '}}' ({close_brace}) in '{line}'"
                    )

                quotes = line.count('"')
                if quotes % 2 != 0:
                    errors.append(f"Mermaid block #{idx} line {l_idx}: Unmatched double quote in '{line}'")

        return errors


class ArtifactSyntaxValidator:
    """
    Programmatic syntax fail-safe validator for synthesized multi-file artifacts.
    Validates standalone JSON files and Mermaid diagram code before writing to disk.
    """
    VALID_MERMAID_HEADERS = (
        "graph ",
        "flowchart ",
        "sequencediagram",
        "classdiagram",
        "statediagram",
        "erdiagram",
        "gantt",
        "pie",
        "mindmap",
    )
    VALID_ORIENTATIONS = ("td", "tb", "bt", "rl", "lr")

    @classmethod
    def validate_artifact(cls, filename: str, content: str) -> List[str]:
        """Validates file content based on extension or artifact type before writing to disk."""
        errors: List[str] = []
        if not content.strip():
            return [f"Artifact '{filename}' is empty."]

        lower_name = filename.lower()
        if lower_name.endswith(".json"):
            try:
                import json
                json.loads(content)
            except Exception as e:
                errors.append(f"Invalid JSON syntax in '{filename}': {str(e)}")

        elif lower_name.endswith(".mmd") or "```mermaid" in content:
            code_to_check = content
            if "```mermaid" in content:
                blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", content, re.DOTALL | re.IGNORECASE)
                code_to_check = "\n".join(blocks) if blocks else content

            lines = [line.strip() for line in code_to_check.splitlines() if line.strip() and not line.strip().startswith("%%")]
            if not lines:
                errors.append(f"Mermaid diagram in '{filename}' has no renderable code lines.")
                return errors

            first_line = lines[0].lower()
            if not any(first_line.startswith(hdr) for hdr in cls.VALID_MERMAID_HEADERS):
                errors.append(
                    f"Mermaid diagram in '{filename}' has invalid header line: '{lines[0]}'. Must start with a valid header keyword."
                )
            elif first_line.startswith("graph ") or first_line.startswith("flowchart "):
                parts = lines[0].split()
                if len(parts) < 2 or parts[1].lower() not in cls.VALID_ORIENTATIONS:
                    errors.append(
                        f"Mermaid graph/flowchart in '{filename}' missing valid orientation keyword (TD, LR, TB, RL, BT)."
                    )

            open_sq = code_to_check.count("[")
            close_sq = code_to_check.count("]")
            if open_sq != close_sq:
                errors.append(f"Mismatched square brackets '[' ({open_sq}) vs ']' ({close_sq}) in '{filename}'.")

            open_paren = code_to_check.count("(")
            close_paren = code_to_check.count(")")
            if open_paren != close_paren:
                errors.append(f"Mismatched parentheses '(' ({open_paren}) vs ')' ({close_paren}) in '{filename}'.")

            open_brace = code_to_check.count("{")
            close_brace = code_to_check.count("}")
            if open_brace != close_brace:
                errors.append(f"Mismatched curly braces '{{' ({open_brace}) vs '}}' ({close_brace}) in '{filename}'.")

            for l_idx, line in enumerate(lines, start=1):
                if re.search(r"(-->|-\.->|==>)\s*$", line):
                    errors.append(f"Line {l_idx} in '{filename}' ends with dangling connector string '{line}'.")

        return errors


class LeftShiftedBlueprintPipeline:
    """
    Executes the 4-layer Left-Shifted Blueprint Sensor suite ("Keep Quality Left").
    Stops at the first failing layer and formats an actionable back-pressure prompt.
    """

    @classmethod
    def run_pipeline(
        cls,
        payload: Dict[str, Any],
        project_id: str,
        epistemic_scratchpad: Optional[EpistemicScratchpad] = None,
    ) -> SensorResult:
        """Runs Layers 0 through 3 on an incoming architectural proposal payload."""
        # Layer 0: Envelope Schema Sensor
        try:
            envelope = DebateRoundEnvelope.model_validate(payload)
        except Exception as e:
            err_msg = f"Envelope Schema validation failed: {str(e)}"
            return cls._build_failure("Layer 0: Envelope Schema", [err_msg])

        proposal_text = envelope.proposal

        # Layer 1: Diagram Syntax Sensor
        diagram_errors = DiagramSyntaxSensor.validate_diagrams(proposal_text)
        if diagram_errors:
            return cls._build_failure("Layer 1: Diagram Syntax", diagram_errors)

        # Layer 2: Epistemic Consistency Sensor
        if epistemic_scratchpad:
            conflict = epistemic_scratchpad.check_contradiction(proposal_text)
            if conflict:
                err_msg = (
                    f"Proposal contradicts Epistemic Scratchpad fact '{conflict.fact_id}' verified by "
                    f"{conflict.verifier}: '{conflict.statement}'"
                )
                return cls._build_failure("Layer 2: Epistemic Consistency", [err_msg])

        return SensorResult(passed=True)

    @classmethod
    def validate_pillar_scores(cls, scores_data: Dict[str, Any]) -> SensorResult:
        """
        Layer 3: Pillar Bounds Sensor.
        Validates that numerical scores fall in [0.0, 1.0] adhering to our quality score convention.
        """
        try:
            scores = PillarScores.model_validate(scores_data)
            return SensorResult(passed=True)
        except Exception as e:
            return cls._build_failure("Layer 3: Pillar Bounds", [f"Invalid PillarScores values: {str(e)}"])

    @classmethod
    def enforce_sensor_guardrails(
        cls,
        payload: Dict[str, Any],
        project_id: str,
        epistemic_scratchpad: Optional[EpistemicScratchpad] = None,
    ) -> Tuple[bool, Optional[str], SensorResult]:
        """
        Executes left-shifted sensor pipeline on an envelope payload.
        Returns a tuple of (passed: bool, backpressure_prompt: Optional[str], result: SensorResult)
        for automated interception and retry prompting.
        """
        result = cls.run_pipeline(payload=payload, project_id=project_id, epistemic_scratchpad=epistemic_scratchpad)
        return result.passed, result.formatted_backpressure, result

    @staticmethod
    def _build_failure(layer_name: str, errors: List[str]) -> SensorResult:
        err_block = "\n".join(f"- {e}" for e in errors)
        backpressure = (
            f"[HARNESS AUTOMATED SENSOR INTERCEPTION]\n"
            f"Your proposed architectural draft failed left-shifted verification at {layer_name}.\n\n"
            f"### Detected Errors:\n{err_block}\n\n"
            f"### Action Required:\n"
            f"Please repair the structural syntax or consistency errors above and output a corrected proposal."
        )
        return SensorResult(
            passed=False,
            failed_layer=layer_name,
            errors=errors,
            formatted_backpressure=backpressure,
        )


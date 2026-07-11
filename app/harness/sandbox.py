import logging
from typing import Any, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LeadArchitectWorkspace:
    """
    Specialized sandbox for Lead Architect.
    Equipped with architectural pattern catalogs and cloud topology references.
    """

    PATTERNS_CATALOG = {
        "event_sourcing": "Immutable append-only domain events with CQRS read projections.",
        "clean_architecture": "Strict dependency inversion separating domain logic from external I/O.",
        "cell_based_routing": "Independent fault-isolated cells for high-scale horizontal scalability.",
    }

    CLOUD_REFERENCES = {
        "aws_serverless": ["API Gateway", "Lambda", "DynamoDB", "EventBridge"],
        "gcp_container": ["Cloud Run", "Cloud SQL PostgreSQL", "Pub/Sub", "Memorystore"],
        "hybrid_kubernetes": ["EKS / GKE", "Istio Service Mesh", "PostgreSQL HA Cluster", "Kafka"],
    }

    @classmethod
    def get_pattern_catalog(cls) -> Dict[str, str]:
        """Returns catalog of architectural patterns."""
        return cls.PATTERNS_CATALOG

    @classmethod
    def get_cloud_reference(cls, pattern_key: str) -> List[str]:
        """Returns recommended cloud components for a reference pattern."""
        return cls.CLOUD_REFERENCES.get(pattern_key.lower(), [])

    @classmethod
    def get_prompt_injection(cls, context_str: str = "") -> str:
        """Returns lightweight instructions advising agent to invoke lookup_architectural_pattern tool."""
        return (
            "Available Harness Tools: Use `lookup_architectural_pattern(pattern_name)` "
            "to query reference architecture patterns and cloud component topologies."
        )


class SecurityAuditorWorkspace:
    """
    Specialized sandbox for Security Auditor.
    Loaded with OWASP threat templates and compliance frameworks (SOC2, GDPR, HIPAA).
    """

    STRIDE_VECTORS = {
        "Spoofing": "Authentication bypass or forged identity tokens.",
        "Tampering": "Unauthorized modification of data in transit or at rest.",
        "Repudiation": "Lack of cryptographic audit logs for sensitive actions.",
        "Information_Disclosure": "Leaking PII/secrets via error stack traces or insecure storage.",
        "Denial_of_Service": "Resource exhaustion or missing rate limiting.",
        "Elevation_of_Privilege": "RBAC/ABAC authorization bypass.",
    }

    COMPLIANCE_CHECKLISTS = {
        "soc2": ["MFA enforced on admin access", "Encrypted audit logging", "Least privilege IAM"],
        "gdpr": ["Right to erasure / anonymization workflow", "Explicit user consent tracking", "EU data residency"],
        "hipaa": ["PHI encryption at rest and transit", "BAA compliant infrastructure", "Strict role-based access"],
    }

    @classmethod
    def get_owasp_threat_vectors(cls) -> Dict[str, str]:
        """Returns STRIDE/OWASP threat vector definitions."""
        return cls.STRIDE_VECTORS

    @classmethod
    def get_compliance_checklist(cls, framework: str) -> List[str]:
        """Returns compliance checklist items for specified framework."""
        return cls.COMPLIANCE_CHECKLISTS.get(framework.lower(), [])

    @classmethod
    def get_prompt_injection(cls, context_str: str = "") -> str:
        """Returns lightweight instructions advising agent to invoke check_owasp_stride_vector or check_compliance_checklist tools."""
        return (
            "Available Harness Tools: Use `check_owasp_stride_vector(vector_name)` or "
            "`check_compliance_checklist(framework)` to query security and compliance standards."
        )


class SREAuditorWorkspace:
    """
    Specialized sandbox for SRE Auditor.
    Equipped with composite availability calculators and failure-mode checklists.
    """

    FAILURE_MODES = [
        "Circuit Breaker threshold and fallback behavior",
        "Token bucket / Leaky bucket rate limiting per IP/tenant",
        "Exponential backoff with jitter on transient I/O retries",
        "Database connection pooling and query timeout bounds",
        "Disaster recovery multi-zone failover RTO/RPO targets",
    ]

    @staticmethod
    def calculate_composite_availability(component_slas: List[float]) -> float:
        """
        Calculates composite availability for serial critical-path dependencies:
        A_total = A_1 * A_2 * ... * A_n
        """
        if not component_slas:
            return 0.0
        composite = 1.0
        for sla in component_slas:
            # Normalize percentage values (e.g., 99.9 -> 0.999)
            norm = sla / 100.0 if sla > 1.0 else sla
            composite *= norm
        return round(composite, 6)

    @classmethod
    def get_failure_mode_checklist(cls) -> List[str]:
        """Returns SRE resilience failure-mode checklist."""
        return cls.FAILURE_MODES

    @classmethod
    def get_prompt_injection(cls, context_str: str = "") -> str:
        """Returns lightweight instructions advising agent to check SRE checklists or verified facts."""
        return (
            "Available Harness Tools: Use `query_verified_facts(project_id)` or "
            "`read_skill('sre')` to verify resilience and availability SLAs."
        )

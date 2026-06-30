import os
import google.auth
from pydantic import BaseModel, Field
from typing import Optional

class AppConfig(BaseModel):
    project_id: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    location: str = Field(default="global")
    use_vertex_ai: bool = Field(default=True)
    developer_knowledge_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("DEVELOPER_KNOWLEDGE_API_KEY"))
    model_id: str = Field(default="gemini-3-flash-preview")
    gate_threshold: float = Field(default=0.85)
    max_rounds: int = Field(default=10)

    @classmethod
    def load_and_validate(cls) -> "AppConfig":
        """Loads configuration from environment variables and validates it, failing fast."""
        # Auto-detect GCP project if not set
        if not os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                _, project_id = google.auth.default()
                os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
            except Exception as e:
                # Fallback gracefully or log
                pass
        
        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
        
        # Instantiate and validate Pydantic fields
        config = cls(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            location="global",
            use_vertex_ai=os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ["true", "1"],
            developer_knowledge_api_key=os.getenv("DEVELOPER_KNOWLEDGE_API_KEY"),
            model_id=os.getenv("DEBATE_MODEL_ID", "gemini-3-flash-preview"),
            gate_threshold=float(os.getenv("DEBATE_GATE_THRESHOLD", "0.85")),
            max_rounds=int(os.getenv("DEBATE_MAX_ROUNDS", "10")),
        )
        
        if not config.project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT environment variable is missing and could not be auto-detected. "
                "Please configure your Google Cloud credentials or set GOOGLE_CLOUD_PROJECT."
            )
            
        return config

# Solitary global config instance loaded and validated at import time
settings = AppConfig.load_and_validate()

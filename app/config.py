import os
from typing import Optional

import google.auth
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    project_id: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    location: str = Field(default="global")
    use_vertex_ai: bool = Field(default=False)
    developer_knowledge_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("DEVELOPER_KNOWLEDGE_API_KEY"))
    model_id: str = Field(default="gemini-3.5-flash")
    grill_model_id: str = Field(default="gemini-3.5-flash")
    auditor_model_id: str = Field(default="gemini-3.5-flash")
    judge_model_id: str = Field(default="gemini-3.1-pro-preview")
    synthesizer_model_id: str = Field(default="gemini-3.1-pro-preview")
    summarizer_model_id: str = Field(default="gemini-3.1-flash-lite")
    gate_threshold: float = Field(default=0.85)
    max_rounds: int = Field(default=10)
    mock_mode: bool = Field(default=False)

    def get_genai_client(self) -> genai.Client:
        """Creates a Google GenAI Client configured for either Vertex AI or standard Gemini API."""
        if self.use_vertex_ai:
            return genai.Client(vertexai=True, project=self.project_id, location=self.location)
        return genai.Client(vertexai=False, api_key=os.getenv("GEMINI_API_KEY"))

    @classmethod
    def load_and_validate(cls) -> "AppConfig":
        """Loads configuration from environment variables and validates it, failing fast."""
        # Ensure environment variables are loaded from root and frontend .env files
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(root_dir, ".env"))
        # load_dotenv(os.path.join(root_dir, "frontend", ".env"))
        load_dotenv()

        # Auto-detect GCP project if not set
        if not os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                _, project_id = google.auth.default()
                os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
            except Exception as e:  # noqa: F841
                # Fallback gracefully or log
                pass

        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

        # Instantiate and validate Pydantic fields
        config = cls(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            location="global",
            use_vertex_ai=os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "False").lower() in ["true", "1"],
            developer_knowledge_api_key=os.getenv("DEVELOPER_KNOWLEDGE_API_KEY"),
            model_id=os.getenv("DEBATE_MODEL_ID", "gemini-3.5-flash"),
            grill_model_id=os.getenv("GRILL_MODEL_ID", "gemini-3.5-flash"),
            auditor_model_id=os.getenv("AUDITOR_MODEL_ID", "gemini-3.5-flash"),
            judge_model_id=os.getenv("JUDGE_MODEL_ID", "gemini-3.1-pro-preview"),
            synthesizer_model_id=os.getenv("SYNTHESIZER_MODEL_ID", "gemini-3.1-pro-preview"),
            gate_threshold=float(os.getenv("DEBATE_GATE_THRESHOLD", "0.85")),
            max_rounds=int(os.getenv("DEBATE_MAX_ROUNDS", "5")),
            mock_mode=os.getenv("MOCK_MODE", "False").lower() in ["true", "1", "yes"],
        )

        if config.use_vertex_ai and not config.project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT environment variable is missing and could not be auto-detected. "
                "Please configure your Google Cloud credentials or set GOOGLE_CLOUD_PROJECT."
            )
        elif not config.use_vertex_ai and not os.getenv("GEMINI_API_KEY"):
            raise ValueError(
                "GEMINI_API_KEY environment variable is missing. "
                "When not using Vertex AI, please provide a valid GEMINI_API_KEY in your .env file."
            )

        return config

# Solitary global config instance loaded and validated at import time
settings = AppConfig.load_and_validate()

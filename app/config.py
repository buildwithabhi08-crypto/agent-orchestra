"""Configuration and settings for Agent Orchestra."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    google_ai_studio_api_key: str = ""
    openrouter_api_key: str = ""

    # Model configuration
    gemini_model: str = "gemini-2.5-pro"
    kimi_model: str = "moonshotai/kimi-k2.5"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Application settings
    app_name: str = "Agent Orchestra"
    workspace_dir: str = str(Path.home() / "agent-orchestra-workspace")
    skills_dir: str = str(Path(__file__).parent.parent / "skills")

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


# Agent-to-model mapping
AGENT_MODEL_MAP: dict[str, str] = {
    "orchestrator": "gemini",
    "developer": "kimi",
    "market_researcher": "gemini",
    "competitive_analyst": "gemini",
    "marketing": "kimi",
    "prevalidation": "gemini",
    "lead_gen": "kimi",
}

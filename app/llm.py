"""LLM client factory for Gemini and Kimi K2.5."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import AGENT_MODEL_MAP, get_settings


def create_gemini_client() -> BaseChatModel:
    """Create a Gemini 2.5 Pro client via Google AI Studio."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_ai_studio_api_key,
        temperature=0.7,
        max_output_tokens=8192,
    )


def create_kimi_client() -> BaseChatModel:
    """Create a Kimi K2.5 client via OpenRouter."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.kimi_model,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=settings.openrouter_base_url,
        temperature=0.7,
        max_tokens=8192,
        default_headers={
            "HTTP-Referer": "https://github.com/ALPHA0008/agent-orchestra",
            "X-Title": "Agent Orchestra",
        },
    )


def get_llm_for_agent(agent_role: str) -> BaseChatModel:
    """Get the appropriate LLM client for a given agent role."""
    model_type = AGENT_MODEL_MAP.get(agent_role, "gemini")
    if model_type == "gemini":
        return create_gemini_client()
    elif model_type == "kimi":
        return create_kimi_client()
    else:
        raise ValueError(f"Unknown model type: {model_type}")

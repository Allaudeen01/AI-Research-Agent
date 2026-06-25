"""
LLM client factory.

Reads LLM_PROVIDER from the environment (default: "groq") and returns
a configured client + the model name to use.

Supported providers
-------------------
  groq   — Groq Cloud (default, fastest)
  openai — OpenAI API

Usage
-----
  from agent.llm_client import get_client
  client, model = get_client()
  response = client.chat.completions.create(model=model, messages=[...])

Environment variables
---------------------
  LLM_PROVIDER      : "groq" | "openai"          (default: groq)
  GROQ_API_KEY      : required when provider=groq
  GROQ_MODEL        : override default groq model  (default: llama-3.3-70b-versatile)
  OPENAI_API_KEY    : required when provider=openai
  OPENAI_MODEL      : override default openai model (default: gpt-4o-mini)
"""

import os


# Current Groq production models (as of June 2025)
# openai/gpt-oss-20b  — fastest (1000 tps), cheapest, great for tool calling
# openai/gpt-oss-120b — most capable (500 tps), best for complex queries
DEFAULT_GROQ_MODEL   = "openai/gpt-oss-20b"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def get_client():
    """
    Returns (client, model_name) for the configured LLM provider.
    The client object is OpenAI-compatible in both cases.
    """
    provider = os.environ.get("LLM_PROVIDER", "groq").lower().strip()

    if provider == "groq":
        return _groq_client()
    elif provider == "openai":
        return _openai_client()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. Choose 'groq' or 'openai'."
        )


def _groq_client():
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package not installed. Run: pip install groq"
        )

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable not set.\n"
            "Get a free key at https://console.groq.com/keys"
        )

    model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    client = Groq(api_key=api_key)
    return client, model


def _openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package not installed. Run: pip install openai"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set.\n"
            "Get a key at https://platform.openai.com/api-keys"
        )

    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    client = OpenAI(api_key=api_key)
    return client, model


def provider_info() -> dict:
    """Return a summary of the active provider config (safe to display in UI)."""
    provider = os.environ.get("LLM_PROVIDER", "groq").lower().strip()
    if provider == "groq":
        model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        return {"provider": "Groq", "model": model, "icon": "⚡"}
    else:
        model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        return {"provider": "OpenAI", "model": model, "icon": "🤖"}

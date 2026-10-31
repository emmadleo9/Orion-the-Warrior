"""Orion Self-Writer — model loader.

Factory that loads the best available free code-writing model for Orion's
self-writing module.

Preference order (all 100% free, no paid OpenAI API):
    1. Local Ollama — Qwen2.5-Coder 32B Instruct / DeepSeek-Coder-V2
    2. OpenRouter free tier — qwen/qwen2.5-coder-32b-instruct:free

Usage:
    from orion.core.self_writer.model_loader import load_model_client
    client = load_model_client()
    print(client.available())
"""

from __future__ import annotations

from .model_client import ModelClient, ModelClientError


def load_model_client() -> ModelClient:
    """Instantiate and return the code-writing model client.

    The client itself decides at request time whether to use local Ollama or
    fall back to OpenRouter. This function only constructs it; it does not
    require a network connection unless you call chat().
    """
    return ModelClient()


def best_available_model() -> ModelClient:
    """Alias for load_model_client (kept for readability in call sites)."""
    return load_model_client()


__all__ = ["load_model_client", "best_available_model", "ModelClient", "ModelClientError"]

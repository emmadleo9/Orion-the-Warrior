"""Orion Self-Writer — LLM provider abstraction.

Provides a free, local-first code-writing model for rewriting Orion's own code.

Primary (local, free, no API key):
    Ollama chat API with Qwen2.5-Coder 32B Instruct (or DeepSeek-Coder-V2).
    Pull it once with:  ollama pull qwen2.5-coder:32b

Fallback (free tier, no dedicated key needed via OpenRouter's free models):
    OpenRouter ``/chat/completions`` using ``qwen/qwen2.5-coder-32b-instruct:free``.

If neither is reachable, the client degrades gracefully and reports the problem
so the admin can install Ollama or set ``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelClientError(RuntimeError):
    """Raised when no code-writing model is available."""


@dataclass
class ChatMessage:
    role: str
    content: str


class ModelClient:
    """Chat-completion client for code generation and self-correction.

    Preference order:
        1. Local Ollama (free, private, no API key)
        2. OpenRouter free tier (free models, optional API key)
    """

    def __init__(self) -> None:
        self.ollama_url = os.getenv("ORION_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.getenv(
            "ORION_SELFWRITER_MODEL",
            "qwen2.5-coder:32b",
        )
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.openrouter_model = os.getenv(
            "ORION_SELFWRITER_OPENROUTER_MODEL",
            "qwen/qwen2.5-coder-32b-instruct:free",
        )
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.context_size = max(4096, int(os.getenv("ORION_SELFWRITER_CONTEXT", "16384")))
        self.max_predict_tokens = max(512, int(os.getenv("ORION_SELFWRITER_MAX_TOKENS", "2048")))

        # Resolve the best installed Ollama code-writing model at construction
        # time so Orion works out of the box (e.g. qwen2.5-coder:7b when 32b
        # is too large for the host). Falls back to the configured model name.
        self.ollama_model = self._resolve_ollama_model(self.ollama_model)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str:
        """Return a chat completion, trying Ollama first then OpenRouter."""
        payload = [{"role": m.role, "content": m.content} for m in messages]

        last_error: Optional[Exception] = None

        # 1. Local Ollama (preferred — 100% free, no key)
        try:
            return self._chat_ollama(payload, temperature)
        except ModelClientError as exc:
            last_error = exc

        # 2. OpenRouter free tier fallback
        try:
            return self._chat_openrouter(payload, temperature)
        except ModelClientError as exc:
            last_error = exc

        raise ModelClientError(
            "No code-writing model available. Install Ollama and pull "
            "qwen2.5-coder:32b (ollama pull qwen2.5-coder:32b), or set "
            "OPENROUTER_API_KEY for the free OpenRouter fallback. "
            f"Last error: {last_error}"
        )

    def available(self) -> dict:
        """Report which providers are reachable (for the admin UI)."""
        ollama_ok = self._provider_ok("ollama")
        openrouter_ok = self._provider_ok("openrouter")
        return {
            "ollama": {
                "reachable": ollama_ok,
                "model": self.ollama_model,
                "url": self.ollama_url,
            },
            "openrouter": {
                "reachable": openrouter_ok,
                "model": self.openrouter_model,
                "has_key": bool(self.openrouter_api_key),
            },
            "any_available": ollama_ok or openrouter_ok,
        }

    # ------------------------------------------------------------------ #
    # Ollama provider
    # ------------------------------------------------------------------ #
    def _resolve_ollama_model(self, preferred: str) -> str:
        """Pick the best installed Ollama code-writing model.

        Returns ``preferred`` if it is installed, otherwise any installed
        model whose name starts with ``qwen2.5-coder`` (preferring 32b, then
        14b, then 7b, then 3b), otherwise ``preferred`` unchanged so Ollama
        can attempt to pull it on first use.
        """
        try:
            req = Request(f"{self.ollama_url}/api/tags", method="GET")
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return preferred

        installed = [
            m.get("name", "")
            for m in data.get("models", [])
            if isinstance(m, dict)
        ]

        def _installed(name: str) -> bool:
            return name in installed

        if _installed(preferred):
            return preferred

        # Preference order for code-writing models.
        for size in ("32b", "14b", "7b", "3b"):
            candidate = f"qwen2.5-coder:{size}"
            if _installed(candidate):
                return candidate
        # Fallback: any qwen2.5-coder variant.
        for name in installed:
            if name.startswith("qwen2.5-coder:"):
                return name
        return preferred
    def _provider_ok(self, provider: str) -> bool:
        if provider == "ollama":
            try:
                req = Request(f"{self.ollama_url}/api/tags", method="GET")
                with urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                installed = [m.get("name", "") for m in data.get("models", [])]
                return any(
                    self.ollama_model.split(":")[0] == name.split(":")[0]
                    for name in installed
                )
            except Exception:
                return False
        if provider == "openrouter":
            # OpenRouter has no cheap health endpoint without a key; just report
            # whether a key is configured so the UI can offer it as an option.
            return bool(self.openrouter_api_key)
        return False

    def _chat_ollama(self, messages: list[dict], temperature: float) -> str:
        body = json.dumps(
            {
                "model": self.ollama_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": temperature,
                    "num_ctx": self.context_size,
                    "num_predict": self.max_predict_tokens,
                },
            }
        ).encode("utf-8")
        request = Request(
            f"{self.ollama_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=300) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelClientError(f"Ollama returned HTTP {exc.code}: {detail[:500]}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelClientError(
                f"Cannot reach Ollama at {self.ollama_url}. Start Ollama and pull the model."
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ModelClientError("Ollama returned an invalid response.") from exc

        if not isinstance(raw, dict):
            raise ModelClientError("Ollama returned an invalid response.")
        message = raw.get("message", {})
        content = message.get("content", "").strip()
        if not content:
            raise ModelClientError("Ollama returned an empty completion.")
        return content

    # ------------------------------------------------------------------ #
    # OpenRouter free-tier provider
    # ------------------------------------------------------------------ #
    def _chat_openrouter(self, messages: list[dict], temperature: float) -> str:
        if not self.openrouter_api_key:
            raise ModelClientError("OpenRouter API key not configured.")

        body = json.dumps(
            {
                "model": self.openrouter_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": self.max_predict_tokens,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Orion the Warrior Self-Writer",
        }
        request = Request(
            self.openrouter_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=300) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelClientError(
                f"OpenRouter returned HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelClientError(
                "Cannot reach OpenRouter. Check your internet connection."
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ModelClientError("OpenRouter returned an invalid response.") from exc

        choices = raw.get("choices", [])
        if not choices:
            raise ModelClientError("OpenRouter returned no choices.")
        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            raise ModelClientError("OpenRouter returned an empty completion.")
        return content

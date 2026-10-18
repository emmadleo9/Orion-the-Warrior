"""Orion Self-Writing Module.

Admin-gated module that lets Orion rewrite and upgrade its own code from a
natural-language command. It uses a free, local code-writing model (Ollama
Qwen2.5-Coder / DeepSeek-Coder-V2, with OpenRouter free-tier fallback), scans
the current codebase, generates new code, tests it in a sandbox, auto-fixes
errors, and only applies changes after admin approval.

Public surface:
    - model_client: LLM provider abstraction (Ollama + OpenRouter fallback)
    - model_loader: model loader factory
    - codebase_scanner: reads the current Orion source tree
    - sandbox: AST + build validation with auto-fix loop
    - diff_utils: unified diff of old vs new code
    - self_writer: the high-level write_code / rewrite orchestration
"""

from .self_writer import SelfWriter, WriteResult, write_code

__all__ = [
    "model_client",
    "model_loader",
    "codebase_scanner",
    "sandbox",
    "diff_utils",
    "self_writer",
    "SelfWriter",
    "WriteResult",
    "write_code",
]
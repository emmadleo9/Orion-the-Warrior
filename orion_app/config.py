"""Load local environment configuration for Orion.

Orion is normally started through ``start_orion.bat`` / ``python main.py``, which
read environment variables from the shell. For convenience this module also
loads a ``.env`` file from the project root, if one exists, so credentials such
as ``ORION_INSTAGRAM_APP_ID`` can live in a single git-ignored file.

The loader is dependency-free (no python-dotenv required) and never overrides a
variable that is already set in the real environment, so shell/CI configuration
always wins over the file.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

_loaded = False


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: Path | None = None, *, override: bool = False) -> bool:
    """Load ``KEY=VALUE`` pairs from an env file into ``os.environ``.

    Returns ``True`` when a file was found and read. Existing environment
    variables are preserved unless ``override`` is true.
    """
    target = Path(path) if path is not None else ENV_FILE
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        value = _strip_quotes(value.strip())
        if override or key not in os.environ:
            os.environ[key] = value
    return True


def load_config() -> bool:
    """Load the project ``.env`` once per process. Safe to call repeatedly."""
    global _loaded
    if _loaded:
        return False
    _loaded = True
    return load_env_file()


load_config()
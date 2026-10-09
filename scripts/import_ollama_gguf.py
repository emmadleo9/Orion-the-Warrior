from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a local GGUF model into Ollama.")
    parser.add_argument("gguf_path", type=Path)
    parser.add_argument("--name", default="orion-qwen-fast")
    args = parser.parse_args()

    model_path = args.gguf_path.expanduser().resolve()
    if not model_path.is_file() or model_path.suffix.lower() != ".gguf":
        parser.error(f"GGUF model file not found: {model_path}")

    ollama_path = shutil.which("ollama")
    if ollama_path is None:
        local_ollama = Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if local_ollama.is_file():
            ollama_path = str(local_ollama)
    if ollama_path is None:
        raise SystemExit("Ollama CLI was not found. Install Ollama and retry.")

    with tempfile.TemporaryDirectory(prefix="orion-ollama-") as temporary_directory:
        modelfile = Path(temporary_directory) / "Modelfile"
        modelfile.write_text(
            f'FROM "{model_path.as_posix()}"\nPARAMETER num_ctx 2048\nPARAMETER num_predict 256\n',
            encoding="utf-8",
        )
        subprocess.run(
            [ollama_path, "create", args.name, "-f", str(modelfile)],
            check=True,
            timeout=600,
        )
    print(f"Model name: {args.name}")


if __name__ == "__main__":
    main()

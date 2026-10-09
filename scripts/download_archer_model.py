from __future__ import annotations

import os

from huggingface_hub import snapshot_download


MODEL_ID = os.getenv("ORION_ARCHER_MODEL", "stabilityai/sd-turbo")
MODEL_FILES = [
    "model_index.json",
    "scheduler/*",
    "text_encoder/config.json",
    "text_encoder/model.fp16.safetensors",
    "tokenizer/*",
    "unet/config.json",
    "unet/diffusion_pytorch_model.fp16.safetensors",
    "vae/config.json",
    "vae/diffusion_pytorch_model.fp16.safetensors",
]


def main() -> None:
    model_path = snapshot_download(repo_id=MODEL_ID, allow_patterns=MODEL_FILES)
    print(f"Archer model ready: {MODEL_ID}")
    print(f"Cached at: {model_path}")


if __name__ == "__main__":
    main()

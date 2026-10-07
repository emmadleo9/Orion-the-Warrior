from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw


class NicoAssistant:
    def __init__(self, name: str = "Nico de Angelo", output_dir: str = "generated") -> None:
        self.name = name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def respond(self, prompt: str) -> dict:
        cleaned_prompt = (prompt or "").strip() or "No task was provided."
        summary = (
            "Summary\n"
            "- Review all active conversations, alerts, and tasks first.\n"
            "- Prioritize the most urgent communication and the deadlines that matter the most.\n"
            "- Keep a close watch on security and device health before executing a broad action.\n"
            "\n"
            "Next action\n"
            "- Open the app or workflow relating to the user's request.\n"
            "- Create or queue the next task in the device pipeline.\n"
            "- Ask for any missing credentials, approvals, or permissions before acting externally."
        )

        return {
            "assistant_name": self.name,
            "prompt": cleaned_prompt,
            "message": summary.replace("the user's request", cleaned_prompt),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def generate_image(self, prompt: str, width: int = 1280, height: int = 720) -> dict:
        image = Image.new("RGBA", (width, height), (18, 24, 36, 255))
        draw = ImageDraw.Draw(image)

        for i in range(height):
            color = (32 + (i * 2) % 80, 40 + (i * 3) % 60, 90 + (i * 4) % 50, 255)
            draw.line((0, i, width, i), fill=color)

        for x in range(0, width, 180):
            draw.rounded_rectangle((x, 80, x + 120, height - 80), radius=32, outline=(120, 130, 255, 200), width=4)

        draw.text((90, 90), "Nico de Angelo", fill=(220, 230, 255, 255), anchor=None)
        draw.text((90, 140), f"Prompt: {prompt[:70]}", fill=(200, 210, 255, 220))
        draw.text((90, 220), "Orion the Warrior", fill=(255, 200, 100, 255), font=None)

        file_name = f"orion_{int(datetime.now().timestamp())}.png"
        output_path = self.output_dir / file_name
        image.save(output_path)

        return {
            "assistant_name": self.name,
            "prompt": prompt,
            "status": "generated",
            "path": str(output_path),
        }

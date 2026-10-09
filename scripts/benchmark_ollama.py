from __future__ import annotations

import argparse
import json
import os
import time
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Ollama's first-token and total response time.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--message", default="Reply with only the word ready.")
    parser.add_argument("--tools", action="store_true", help="Include a small function tool schema.")
    parser.add_argument("--threads", type=int)
    args = parser.parse_args()

    tools = []
    if args.tools:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "get_local_time",
                    "description": "Get local time.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )
    body = json.dumps(
        {
            "model": args.model,
            "messages": [{"role": "user", "content": args.message}],
            "tools": tools,
            "stream": True,
            "keep_alive": "30m",
            "options": {
                "num_ctx": 2048,
                "num_predict": 64,
                **({"num_thread": args.threads} if args.threads else {}),
            },
        }
    ).encode("utf-8")
    request = Request(
        f"{os.getenv('ORION_OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_token = None
    chunks = []
    tool_calls = []
    error = None
    with urlopen(request, timeout=180) as response:
        for line in response:
            if not line.strip():
                continue
            event = json.loads(line.decode("utf-8"))
            if event.get("error"):
                error = event["error"]
            message = event.get("message", {})
            if message.get("content"):
                if first_token is None:
                    first_token = time.perf_counter() - started
                chunks.append(message["content"])
            tool_calls.extend(message.get("tool_calls") or [])

    print(
        json.dumps(
            {
                "model": args.model,
                "threads": args.threads,
                "first_content_seconds": round(first_token or 0, 2),
                "total_seconds": round(time.perf_counter() - started, 2),
                "reply": "".join(chunks),
                "tool_calls": tool_calls,
                "error": error,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

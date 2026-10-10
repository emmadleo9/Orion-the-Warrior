import os
import socket
import sys
import webbrowser
import uvicorn

from orion_app.main import app


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    if is_port_in_use(port):
        print(f"\n=======================================================")
        print(f" [!] NOTICE: Port {port} is already in use.")
        print(f" Orion (or another process) is already running at:")
        print(f"     http://localhost:{port}")
        print(f"=======================================================\n")
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
        sys.exit(0)

    uvicorn.run(app, host=host, port=port)
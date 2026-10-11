import os
import socket
import sys
import webbrowser
import uvicorn

from orion_app.config import load_config

load_config()

from orion_app.main import app

def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    if is_port_in_use(port, host):
        print(f"{'='*60}")
        print(f" [!] NOTICE: Port {port} is already in use.")
        print(f" Orion (or another process) is already running at:")
        print(f"     http://localhost:{port}")
        print(f"{'='*60}\n")
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
        sys.exit(0)

    print(f"{'='*60}")
    print(f" Orion The Warrior starting at:")
    print(f"     Local: http://localhost:{port}")
    print(f"     Network: http://192.168.18.144:{port}  <- USE THIS ON PHONE")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port)
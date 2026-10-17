import os
import socket
import sys
import webbrowser
import uvicorn

from orion_app.config import load_config

load_config()

from orion_app.main import app

def get_lan_ips() -> list[str]:
    """Best-effort list of this machine's LAN IPv4 addresses (for the phone URL)."""
    ips: list[str] = []
    try:
        # Opening a UDP socket to a public address reveals the outbound interface
        # without sending any packets.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            primary = s.getsockname()[0]
        if primary and not primary.startswith("127."):
            ips.append(primary)
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass

    return ips or ["localhost"]


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Return True when something is already listening on ``port``.

    Probing ``0.0.0.0`` with ``connect_ex`` does not reliably detect a bound
    socket on Windows, so we probe the loopback address and, additionally, try
    to bind the socket ourselves. A bind failure means the port is taken.
    """
    # Probe loopback: a server bound to 0.0.0.0 is reachable via 127.0.0.1.
    for probe_host in ("127.0.0.1", "localhost"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex((probe_host, port)) == 0:
                    return True
        except OSError:
            pass

    # Authoritative check: if we can bind the port, nobody else holds it.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True

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
    for ip in get_lan_ips():
        print(f"     Network: http://{ip}:{port}  <- USE THIS ON PHONE")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port)
import os
import socket
import sys
import webbrowser
import uvicorn

from orion_app.config import load_config

load_config()

from orion_app.main import app

def is_tailscale_ip(ip: str) -> bool:
    """Check if an IPv4 address belongs to the Tailscale CGNAT range (100.64.0.0/10)."""
    try:
        parts = [int(p) for p in ip.split(".")]
        return len(parts) == 4 and parts[0] == 100 and 64 <= parts[1] <= 127
    except Exception:
        return False


def get_all_ips() -> tuple[list[str], list[str]]:
    """Return (tailscale_ips, lan_ips) for this machine."""
    discovered: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            primary = s.getsockname()[0]
        if primary and not primary.startswith("127."):
            discovered.append(primary)
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in discovered and not ip.startswith("127."):
                discovered.append(ip)
    except OSError:
        pass

    tailscale_ips = [ip for ip in discovered if is_tailscale_ip(ip)]
    lan_ips = [ip for ip in discovered if not is_tailscale_ip(ip) and not ip.startswith("192.168.56.")]
    return tailscale_ips, (lan_ips or ["localhost"])


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

    tailscale_ips, lan_ips = get_all_ips()

    print(f"{'='*60}")
    print(f" Orion The Warrior starting at:")
    print(f"     Local PC:   http://localhost:{port}")
    if tailscale_ips:
        for tip in tailscale_ips:
            print(f"     Tailscale:  http://{tip}:{port}  <- USE THIS ON PHONE (WORLDWIDE)")
    else:
        print(f"     Tailscale:  Not detected. Connect Tailscale to access worldwide.")
    for lip in lan_ips:
        print(f"     Local Wi-Fi: http://{lip}:{port}")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port)
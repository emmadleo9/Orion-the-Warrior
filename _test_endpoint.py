import urllib.request
import json

BASE = "http://127.0.0.1:8000"

def post(path, payload=None):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, body

def get(path):
    req = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

print("=== HEALTH ===")
print(get("/api/health"))

print("\n=== SELF-WRITE STATUS ===")
print(post("/api/self-write/status"))

print("\n=== SELF-WRITE WRITE (dark mode) ===")
code, body = post("/api/self-write/write", {"command": "add a dark mode toggle to the dashboard"})
print("status:", code)
if isinstance(body, dict):
    print("success:", body.get("success"))
    print("message:", body.get("message"))
    if body.get("diff"):
        d = body["diff"]
        print("diff file:", d.get("file_path"))
        print("summary:", d.get("summary"))
        print("is_new_file:", d.get("is_new_file"))
        print("diff preview:", (d.get("unified_diff") or "")[:500])
else:
    print(body)

print("\n=== SELF-WRITE BACKUPS ===")
print(get("/api/self-write/backups"))

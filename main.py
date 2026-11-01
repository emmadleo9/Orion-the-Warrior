import psutil
import platform
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Orion", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/system")
def api_system() -> dict:
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot = psutil.boot_time()
    uptime_sec = int(time.time() - boot)
    h = uptime_sec // 3600
    m = (uptime_sec % 3600) // 60
    return {
        "cpu": cpu,
        "ram": mem.percent,
        "disk": disk.percent,
        "status": "online",
        "cpu_percent": cpu,
        "ram_percent": mem.percent,
        "disk_percent": disk.percent,
        "uptime": f"{h}h {m}m",
        "host": platform.node(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)

from fastapi import APIRouter
import time
import random
import math

router = APIRouter(prefix="/api/anti-gravity")

STATE = {
    "enabled": False,
    "field_strength": 0,
    "gravity": 9.81,
    "stability": 100,
    "power": 0,
    "altitude": 0
}

@router.get("/status")
def status():
    global STATE
    if STATE["enabled"]:
        STATE["gravity"] = -9.81 * (STATE["field_strength"] / 100)
        STATE["altitude"] = STATE["field_strength"] / 10 + random.uniform(-0.1, 0.1)
        STATE["power"] = STATE["field_strength"] * 8 + random.uniform(0, 20)
        STATE["stability"] = max(0, 100 - abs(STATE["gravity"]) * 2 + random.uniform(-2, 2))
    else:
        STATE["gravity"] = 9.81
        STATE["altitude"] = 0
        STATE["power"] = 0
    STATE["timestamp"] = time.time()
    return STATE

@router.post("/toggle")
def toggle():
    STATE["enabled"] = not STATE["enabled"]
    return STATE

@router.post("/set-strength/{value}")
def set_strength(value: int):
    STATE["field_strength"] = max(0, min(100, value))
    return STATE

@router.post("/cut")
def cut():
    STATE["enabled"] = False
    STATE["field_strength"] = 0
    return STATE

@router.post("/stabilize")
def stabilize():
    STATE["stability"] = 100.0
    return STATE

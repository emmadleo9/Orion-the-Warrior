@echo off
cd /d D:\Orion
python -m uvicorn orion_app.main:app --host 127.0.0.1 --port 8000

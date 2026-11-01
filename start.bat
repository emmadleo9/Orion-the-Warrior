@echo off
cd /d D:\Orion

:: Kill any old python processes running main.py/uvicorn
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
timeout /t 2 >nul

:: Start the backend
start "" python main.py

:: Wait briefly for the server to bind, then open the dashboard
timeout /t 4 >nul
start "" "http://127.0.0.1:8000"

@echo off
setlocal
title Orion the Warrior
cd /d "%~dp0"
if errorlevel 1 (
    echo ERROR: Could not open the Orion folder:
    echo "%~dp0"
    goto :failed
)

set "ORION_PYTHON=%~dp0\.venv\Scripts\python.exe"
if not exist "%ORION_PYTHON%" (
    echo ERROR: Orion's virtual environment was not found.
    echo Expected: "%ORION_PYTHON%"
    echo.
    echo From this folder, run:
    echo   py -3 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    goto :failed
)

echo Starting Orion from:
echo "%~dp0"
echo Open http://127.0.0.1:8000 after the server reports startup.
echo Press Ctrl+C in this window to stop Orion.
echo.
"%ORION_PYTHON%" "%~dp0main.py"
set "ORION_EXIT_CODE=%ERRORLEVEL%"
if not "%ORION_EXIT_CODE%"=="0" (
    echo.
    echo ERROR: Orion stopped with exit code %ORION_EXIT_CODE%.
    goto :failed
)
goto :end

:failed
echo.
echo Check the error above. This window will remain open so the details are visible.
pause

:end
endlocal

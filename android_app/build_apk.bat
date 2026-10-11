@echo off
title Orion The Warrior - Android APK Builder
echo ========================================================
echo    Orion - The Warrior : Android Client APK Builder
echo ========================================================
echo.
echo [1] Checking for Android SDK and Gradle...

where gradle >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Gradle found. Building Debug APK...
    call gradle assembleDebug
    if %ERRORLEVEL% equ 0 (
        echo.
        echo ========================================================
        echo [SUCCESS] APK built successfully!
        echo Location: app\build\outputs\apk\debug\app-debug.apk
        echo ========================================================
        pause
        exit /b 0
    )
)

echo.
echo [!] NOTE: To build the APK file directly:
echo.
echo   Option A (Recommended):
echo     1. Open Android Studio
echo     2. Choose "Open an existing project"
echo     3. Select this folder: %CD%
echo     4. Click Build ^> Build Bundle(s) / APK(s) ^> Build APK(s)
echo     5. Transfer the generated app-debug.apk to your phone!
echo.
echo   Option B (Command Line with Android SDK installed):
echo     Run: gradlew assembleDebug
echo.
echo ========================================================
pause


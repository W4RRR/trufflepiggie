@echo off
:: TrufflePiggie - Quick Install Script (Windows)
:: ===============================================

echo.
echo   🐷 TrufflePiggie Installer
echo   ==========================
echo.

:: Install dependencies
echo [*] Installing dependencies...
pip install -q requests rich pyyaml

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Installation complete!
    echo.
    echo Next steps:
    echo   1. Add your GitHub token to: config\tokens\my_token.txt
    echo   2. Run: python trufflepiggie.py -q "target.com" -o results
    echo.
) else (
    echo ❌ Installation failed
    exit /b 1
)


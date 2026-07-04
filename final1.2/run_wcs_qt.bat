@echo off
REM WCS Configuration Tool Launcher (Qt6 Version)
REM Launches the modern PyQt6 interface

cd /d "%~dp0"

echo =============================================================
echo =               WCS Test Configuration Tool                 =
echo =============================================================
echo.
echo Checking Python and PyQt6...

REM Check if PyQt6 is installed
python -c "import PyQt6" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] PyQt6 is not installed!
    echo.
    echo Installing PyQt6...
    python -m pip install PyQt6
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install PyQt6!
        echo Please install manually: pip install PyQt6
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Launching WCS Tool...
echo.

python wcs_qt.py

if errorlevel 1 (
    echo.
    echo [ERROR] Application crashed or exited with error!
    echo.
    pause
)

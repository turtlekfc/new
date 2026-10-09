@echo off
cd /d "%~dp0"

if not exist venv (
    echo Setup has not been run yet. Please double-click setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python main.py %*

if errorlevel 1 (
    echo.
    echo ============================================
    echo   The program reported an error (see above,
    echo   and the app.log file, for details).
    echo ============================================
    pause
)

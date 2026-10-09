@echo off
cd /d "%~dp0"

echo ============================================
echo   Club Ledger - Protected Build (PyArmor)
echo ============================================
echo.
echo This will obfuscate the Python source with PyArmor,
echo package it into ClubLedger.exe with PyInstaller, and
echo assemble a ready-to-zip release folder next to this
echo project folder - containing ONLY what end users should
echo get (the EXE, the user manual, the mobile-entry templates).
echo No README, no source code, no recovery tool.
echo.

if not exist venv (
    echo [ERROR] Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Installing/updating PyArmor and PyInstaller...
pip install -U pyarmor pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install pyarmor/pyinstaller. Check your internet
    echo         connection, then try again.
    pause
    exit /b 1
)

echo.
echo Checking PyArmor license/registration status...
pyarmor --version
echo.
echo IMPORTANT: if PyArmor prints a trial/expiry notice above, the EXE built
echo today may stop working after the trial period ends. See README.md,
echo section "Protected build (PyArmor)" before distributing this build widely.
echo.
pause

echo Removing old obfuscated build folder (if any)...
if exist dist_obf rmdir /s /q dist_obf

echo Obfuscating backend\ and main.py with PyArmor...
pyarmor gen -O dist_obf -r backend main.py
if errorlevel 1 (
    echo [ERROR] PyArmor obfuscation failed. See the messages above.
    pause
    exit /b 1
)

echo Copying frontend\ into the obfuscated build (not Python, not obfuscated)...
xcopy /e /i /y frontend dist_obf\frontend >nul

echo.
set ICON_ARG=
if exist assets\icon.ico (
    echo Found assets\icon.ico, the EXE will use it as its icon.
    set ICON_ARG=--icon "%cd%\assets\icon.ico"
) else (
    echo No assets\icon.ico found, building with the default icon.
    echo ^(see README.md, section "Add a custom icon to the EXE", if you want one^)
)

echo.
echo Running PyInstaller on the obfuscated source...
cd dist_obf
pyinstaller --noconfirm --onefile --windowed --add-data "frontend;frontend" %ICON_ARG% --name ClubLedger main.py
if errorlevel 1 (
    cd ..
    echo [ERROR] PyInstaller failed. See the messages above.
    pause
    exit /b 1
)
cd ..

echo.
echo Assembling the release folder (this is the ONLY folder you need
echo to zip and send out - everything in it is safe to give to end users)...
set RELEASE_DIR=..\ClubLedger_Release
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
if not exist "%RELEASE_DIR%\templates" mkdir "%RELEASE_DIR%\templates"

copy /y dist_obf\dist\ClubLedger.exe "%RELEASE_DIR%\ClubLedger.exe" >nul
copy /y docs\*.html "%RELEASE_DIR%\" >nul
xcopy /e /i /y templates "%RELEASE_DIR%\templates\" >nul

echo.
echo ============================================
echo   Done! Your ready-to-send release folder is at:
echo   %RELEASE_DIR%
echo.
echo   Test ClubLedger.exe inside that folder first
echo   (create a ledger, log in, add a transaction,
echo   backup/restore) before sending it out.
echo.
echo   When ready, just right-click that folder in
echo   File Explorer and choose "Send to ^> Compressed
echo   (zipped) folder" - that's the file to give to
echo   end users. Nothing else needs to be copied by
echo   hand, and nothing from this project folder
echo   (README.md, tools\, source code) is in it.
echo.
echo   Re-run this script any time you rebuild - it
echo   will overwrite the release folder with the
echo   latest EXE and latest docs automatically.
echo ============================================
pause

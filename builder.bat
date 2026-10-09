@echo off
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;%PATH%"
title Python 跨平台打包助手

cd /d "%~dp0"
cls
echo ======================================================
echo    Python 跨平台打包助手 (Win EXE + GitHub Mac APP)
echo ======================================================
echo.

:: 1. 確保基本打包套件已安裝
python -m pip install pyinstaller pyarmor pywebview >nul 2>&1

:: 2. 執行 Python 打包核心
python pack.py

if %errorlevel% neq 0 (
    echo.
    echo 【錯誤】打包失敗，請檢視上方錯誤訊息。
    pause
    exit /b
)

echo.
echo ======================================================
echo 請選擇是否要將專案推送至 GitHub 進行 Mac 雲端打包？
echo [1] 推送至 GitHub (雲端編譯 Mac APP)
echo [2] 結束 (只使用剛剛產出的 Windows EXE)
echo ======================================================
set /p "GIT_CHOICE=請選擇 (1/2): "

if not "%GIT_CHOICE%"=="1" goto :END

:: 3. 確保 GitHub 工作流設定檔存在
if not exist ".github\workflows" mkdir ".github\workflows"
set "YML_PATH=.github\workflows\build_mac.yml"
> "%YML_PATH%" echo name: Cloud Build Mac APP
>>"%YML_PATH%" echo on:
>>"%YML_PATH%" echo   push:
>>"%YML_PATH%" echo     branches: [ "main", "master" ]
>>"%YML_PATH%" echo   workflow_dispatch:
>>"%YML_PATH%" echo jobs:
>>"%YML_PATH%" echo   build-macos:
>>"%YML_PATH%" echo     name: 打包 macOS APP
>>"%YML_PATH%" echo     runs-on: macos-latest
>>"%YML_PATH%" echo     steps:
>>"%YML_PATH%" echo       - uses: actions/checkout@v4
>>"%YML_PATH%" echo       - name: 設定 Python
>>"%YML_PATH%" echo         uses: actions/setup-python@v5
>>"%YML_PATH%" echo         with:
>>"%YML_PATH%" echo           python-version: "3.11"
>>"%YML_PATH%" echo       - name: 安裝相依套件
>>"%YML_PATH%" echo         run: ^|
>>"%YML_PATH%" echo           python -m pip install --upgrade pip
>>"%YML_PATH%" echo           pip install pyinstaller pyarmor pywebview
>>"%YML_PATH%" echo           if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
>>"%YML_PATH%" echo       - name: 原始碼混淆加密
>>"%YML_PATH%" echo         run: ^|
>>"%YML_PATH%" echo           pyarmor gen -O pyarmor_mac_dist main.py backend
>>"%YML_PATH%" echo       - name: 編譯 macOS 應用程式
>>"%YML_PATH%" echo         run: ^|
>>"%YML_PATH%" echo           pyinstaller --noconfirm --windowed --paths "pyarmor_mac_dist" --paths "." --collect-all backend --collect-all pywebview --hidden-import "webview" --hidden-import "backend" --hidden-import "backend.api" --hidden-import "backend.db" --hidden-import "backend.ledger_manager" --hidden-import "sqlite3" --add-data "frontend:frontend" --add-data "templates:templates" --name "MyApp_Mac" pyarmor_mac_dist/main.py
>>"%YML_PATH%" echo           cd dist
>>"%YML_PATH%" echo           zip -r MyApp-macOS.zip MyApp_Mac.app
>>"%YML_PATH%" echo       - name: 上傳成品
>>"%YML_PATH%" echo         uses: actions/upload-artifact@v4
>>"%YML_PATH%" echo         with:
>>"%YML_PATH%" echo           name: macOS-APP
>>"%YML_PATH%" echo           path: dist/MyApp-macOS.zip

:: 4. 推送到 GitHub
echo.
echo [*] 正在推送至 GitHub...
git add .
git commit -m "Trigger cross-platform build via pack.py" >nul 2>&1
git push -u origin main

echo.
echo [V] 專案已成功推送到 GitHub！
echo 請至 GitHub 專案的 [Actions] 頁籤下載 Mac APP 成品。

:END
echo.
echo ======================================================
echo 作業已完成，請按任意鍵離開...
echo ======================================================
pause >nul
@echo off
chcp 65001 >nul
title Photo Authenticator Web

cd /d "%~dp0\..\photo_authenticator"
call venv\Scripts\activate.bat

pip install flask --quiet

echo.
echo =================================
echo   Photo Authenticator Web
echo =================================
echo   Компьютер: http://localhost:5000
echo.
echo   На телефоне откройте:
echo   http://[IP-компьютера]:5000
echo   (IP в настройках Wi-Fi)
echo.
echo   Для остановки закройте окно
echo =================================
echo.

start "" "http://localhost:5000"

cd /d "%~dp0"
python web_app.py
pause

@echo off
chcp 65001 >nul
title Photo Authenticator — Установка для Windows

echo ================================================
echo   Photo Authenticator — Установка для Windows
echo ================================================
echo.

SET APP_DIR=%USERPROFILE%\Desktop\photo_authenticator
SET SCRIPT_DIR=%~dp0

:: Проверяем Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo ❌ Python не найден.
    echo.
    echo Скачайте Python 3.11 с https://www.python.org/downloads/
    echo Во время установки обязательно отметьте "Add Python to PATH"
    echo.
    echo После установки Python запустите этот файл снова.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

FOR /F "tokens=*" %%i IN ('python --version') DO SET PYVER=%%i
echo ✅ %PYVER%

:: Копируем файлы если нужно
IF NOT "%SCRIPT_DIR:~0,-1%"=="%APP_DIR%" (
    echo.
    echo 📁 Копируем файлы...
    xcopy "%SCRIPT_DIR%*" "%APP_DIR%\" /E /I /Y /Q >nul 2>&1
)

cd /d "%APP_DIR%"

:: Создаём виртуальное окружение
IF NOT EXIST "venv\" (
    echo.
    echo 🔧 Создаём виртуальное окружение...
    python -m venv venv
)

call venv\Scripts\activate.bat

:: Устанавливаем зависимости
echo.
echo 📦 Устанавливаем зависимости (1-2 минуты)...
pip install --upgrade pip --quiet
pip install customtkinter Pillow opencv-python imagehash numpy piexif requests aiohttp jinja2 python-dotenv geopy tqdm --quiet

:: Создаём .env если нет
IF NOT EXIST ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo ⚙️  Создан файл .env — добавьте API ключи при необходимости
)

:: Создаём ярлык запуска
SET LAUNCHER=%USERPROFILE%\Desktop\Photo Authenticator.bat
(
echo @echo off
echo cd /d "%APP_DIR%"
echo call venv\Scripts\activate.bat
echo python app.py
) > "%LAUNCHER%"

echo.
echo ================================================
echo   ✅ Установка завершена!
echo ================================================
echo.
echo   Ярлык создан на рабочем столе:
echo   'Photo Authenticator.bat'
echo.
echo   Запускаем программу...
echo.

python app.py
pause

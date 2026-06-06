#!/bin/bash
# Photo Authenticator — Веб-версия
# Запускает веб-сервер и открывает браузер

cd "$(dirname "$0")/../photo_authenticator"
source venv/bin/activate

# Устанавливаем Flask если нет
pip install flask --quiet

echo ""
echo "================================="
echo "  Photo Authenticator Web"
echo "================================="

# Получаем локальный IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

echo "  Компьютер: http://localhost:5000"
echo "  iPhone/Android: http://$LOCAL_IP:5000"
echo ""
echo "  Откройте ссылку на телефоне"
echo "  в той же Wi-Fi сети"
echo ""
echo "  Для остановки нажмите Ctrl+C"
echo "================================="
echo ""

# Открываем браузер через секунду
sleep 1 && open "http://localhost:5000" &

cd "$(dirname "$0")"
python3 web_app.py

#!/bin/bash
# Photo Authenticator — установщик для macOS
# Двойной клик для установки и запуска

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/Desktop/photo_authenticator"

echo "================================================"
echo "  Photo Authenticator — Установка для macOS"
echo "================================================"
echo ""

# Проверяем Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 не найден. Устанавливаем через Homebrew..."
    if ! command -v brew &>/dev/null; then
        echo "Устанавливаем Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python@3.11
fi

PYTHON=$(command -v python3)
echo "✅ Python: $($PYTHON --version)"

# Копируем файлы если нужно
if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
    echo ""
    echo "📁 Копируем файлы в $APP_DIR ..."
    cp -r "$SCRIPT_DIR" "$APP_DIR" 2>/dev/null || true
fi

cd "$APP_DIR"

# Создаём виртуальное окружение
if [ ! -d "venv" ]; then
    echo ""
    echo "🔧 Создаём виртуальное окружение..."
    $PYTHON -m venv venv
fi

source venv/bin/activate

# Устанавливаем зависимости
echo ""
echo "📦 Устанавливаем зависимости (может занять 1-2 минуты)..."
pip install --upgrade pip --quiet
pip install customtkinter Pillow opencv-python imagehash numpy piexif requests aiohttp jinja2 python-dotenv geopy tqdm --quiet

# Создаём .env если нет
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚙️  Создан файл .env — добавьте API ключи при необходимости"
fi

# Создаём ярлык запуска на рабочем столе
LAUNCHER="$HOME/Desktop/Photo Authenticator.command"
cat > "$LAUNCHER" << 'LAUNCH'
#!/bin/bash
cd "$HOME/Desktop/photo_authenticator"
source venv/bin/activate
python3 app.py
LAUNCH
chmod +x "$LAUNCHER"

echo ""
echo "================================================"
echo "  ✅ Установка завершена!"
echo "================================================"
echo ""
echo "  Ярлык создан на рабочем столе:"
echo "  'Photo Authenticator.command'"
echo ""
echo "  Запускаем программу..."
echo ""

python3 app.py

# Photo Authenticator

**Десктопный OSINT/Forensic инструмент для проверки подлинности фотографий.**

> ⚠️ Программа не утверждает «фото точно настоящее» или «фото точно фейк».
> Она даёт вероятностный анализ с объяснением: какие факты найдены, какие сервисы
> дали совпадения, какие признаки вызывают сомнение.

---

## Возможности

| Модуль | Что делает |
|--------|-----------|
| **Метаданные** | Извлекает EXIF/IPTC/XMP, GPS-координаты, данные камеры, признаки редактирования |
| **Forensics** | Error Level Analysis (ELA), анализ JPEG-сжатия, perceptual hashes (pHash/dHash/aHash/wHash), поиск локальных дубликатов |
| **AI-детекция** | Локальные эвристики + интеграции с Hive, Sightengine, Illuminarty |
| **Обратный поиск** | TinEye API, Google Lens + Yandex через SerpAPI, Bing Visual Search |
| **Геолокация** | Reverse geocoding через OpenCage или Nominatim, ссылки на OSM/Google Maps |
| **Отчёты** | HTML с визуализацией, JSON, краткий текст для буфера обмена |
| **История** | SQLite-база всех проверок с быстрым поиском дубликатов |

---

## Установка

### 1. Python 3.11+

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Зависимости

```bash
pip install -r requirements.txt
```

**Опционально — для улучшенного drag&drop:**
```bash
pip install tkinterdnd2
```

**Опционально — OCR текста на изображениях:**
```bash
pip install pytesseract
# + установить Tesseract: https://github.com/tesseract-ocr/tesseract
```

**Опционально — ExifTool (максимальный охват метаданных):**
- Windows: скачать с https://exiftool.org/ и добавить в PATH
- macOS: `brew install exiftool`
- Linux: `sudo apt install libimage-exiftool-perl`

### 3. Настройка API-ключей

```bash
cp .env.example .env
```

Откройте `.env` и заполните нужные ключи:

```env
# Reverse image search
TINEYE_API_KEY=your_key_here
SERPAPI_KEY=your_key_here
BING_SEARCH_KEY=your_key_here

# AI detection
HIVE_API_KEY=your_key_here
SIGHTENGINE_API_USER=your_user
SIGHTENGINE_API_SECRET=your_secret
ILLUMINARTY_API_KEY=your_key_here

# Geocoding (optional)
OPENCAGE_API_KEY=your_key_here
```

> Ключи, которые не заданы, просто пропускаются — приложение работает
> только с доступными сервисами.

### 4. Запуск

```bash
python app.py
```

---

## Получение API-ключей

| Сервис | URL | Бесплатный тариф |
|--------|-----|-----------------|
| TinEye | https://api.tineye.com/ | Платный |
| SerpAPI | https://serpapi.com/ | 100 запросов/месяц |
| Bing Visual Search | https://www.microsoft.com/en-us/bing/apis/ | 1000 запросов/месяц |
| Hive AI | https://hivemoderation.com/ | По запросу |
| Sightengine | https://sightengine.com/ | 2000 запросов/месяц |
| Illuminarty | https://illuminarty.ai/ | Есть бесплатный тариф |
| OpenCage | https://opencagedata.com/ | 2500 запросов/день |

---

## Режимы работы

| Режим | Описание |
|-------|----------|
| **Быстрая** | Метаданные + хэши + базовый forensics + AI-эвристики. Обратный поиск только если есть согласие. |
| **Полная** | Всё вышеперечисленное + все доступные API |
| **Только локально** | Никакие данные не покидают компьютер. Метаданные, ELA, хэши, локальные эвристики. |

Перед отправкой изображения во внешние сервисы приложение всегда запрашивает явное согласие и показывает список сервисов.

---

## Структура проекта

```
photo_authenticator/
├── app.py                  — точка входа
├── config.py               — конфигурация (читает .env)
├── requirements.txt
├── .env.example
├── README.md
│
├── core/
│   ├── models.py           — типизированные модели данных
│   ├── pipeline.py         — главный пайплайн анализа
│   └── risk_score.py       — вычисление многомерной оценки риска
│
├── modules/
│   ├── metadata_extractor.py   — EXIF/IPTC/XMP/GPS
│   ├── hashing.py              — perceptual & cryptographic hashes
│   ├── forensics.py            — ELA, JPEG, манипуляции
│   ├── ai_detection.py         — оркестратор AI-детекции
│   ├── reverse_search.py       — оркестратор обратного поиска
│   ├── geolocation.py          — reverse geocoding
│   └── report_generator.py     — HTML/JSON/текстовые отчёты
│
├── services/
│   ├── tineye_client.py
│   ├── serpapi_client.py       — Google Lens + Yandex
│   ├── bing_client.py
│   ├── hive_client.py
│   ├── sightengine_client.py
│   └── illuminarty_client.py
│
├── ui/
│   ├── main_window.py      — главное окно (CustomTkinter)
│   └── result_tabs.py      — вкладки результатов
│
├── data/
│   ├── database.py         — SQLite история
│   └── history.sqlite      — создаётся автоматически
│
└── tests/
    ├── test_metadata.py
    ├── test_hashing.py
    └── test_pipeline.py
```

---

## Запуск тестов

```bash
pytest tests/ -v
```

---

## Шкалы оценки

Результат не выражается одним числом. Вместо этого используется пять независимых шкал:

| Шкала | Что измеряет |
|-------|-------------|
| **Internet provenance** | Насколько фото известно в интернете |
| **Metadata confidence** | Насколько метаданные полные и непротиворечивые |
| **AI suspicion** | Признаки AI-генерации |
| **Manipulation suspicion** | Признаки ручного редактирования/монтажа |
| **Geolocation confidence** | Достоверность GPS-данных |

Итоговый уровень доверия: **Высокий / Средний / Низкий / Не определён**

---

## Конфиденциальность

- По умолчанию приложение работает **только локально** — никакие данные не отправляются.
- Отправка в API происходит только после явного согласия пользователя.
- API-ключи хранятся в `.env` и никогда не попадают в код.
- Незаконный скрейпинг не используется. Сервисы без официального API открываются в браузере для ручной проверки.

---

## Переход на PyQt

Вся бизнес-логика (core/, modules/, services/) не зависит от Tkinter.
Для миграции на PyQt нужно только переписать `ui/main_window.py` и `ui/result_tabs.py`.
`AnalysisResult` и пайплайн остаются без изменений.

---

## Ограничения

- ELA работает только для JPEG. PNG/WebP будут проанализированы без ELA.
- Отсутствие EXIF **не является доказательством** подделки — мессенджеры и соцсети удаляют метаданные автоматически.
- Все результаты носят вероятностный характер. Это инструмент для журналистов, OSINT-исследователей и верификаторов, а не судебный инструмент.

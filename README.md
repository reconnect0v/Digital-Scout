# DigitalScout — MVP 0.2 (Vercel-ready)

Сервис поиска и сравнения предложений цифровых товаров по маркетплейсам: **Plati.Market**, **GGsel**, **FunPay** и **Playerok**.
Объявления выводятся прямо на сайте единым списком и отсортированы по возрастанию цены.

---

## Статус источников

| Площадка | Статус | Как работает получение данных |
|---|---|---|
| **Plati.Market** | ✅ Подключён | Публичный API каталога (`plati.io/api/search.ashx`). Названия, цены в рублях, ссылки на товары. |
| **GGsel** | ✅ Подключён | Разбор каталога поиска (`ggsel.net` / `ggsel.com`). Карточки с ценами в рублях. |
| **FunPay** | ✅ Подключён | Запрос категорий через `promoFilter` и парсинг живых лотов (`tc-item`) с ценами в ₽. |
| **Playerok** | ⚠️ Защита Cloudflare | Платформа использует Cloudflare Turnstile / GraphQL. Поддерживает передачу сессии через переменную окружения `PLAYEROK_COOKIE`. При блокировке корректно сообщает статус. |

---

## Деплой на Vercel

Проект полностью настроен для деплоя на Vercel:

1. **GitHub**: Изменения отправляются в репозиторий:
   ```bash
   git add .
   git commit -m "Подключение FunPay, исправление Vercel деплоя и Playerok адаптера"
   git push origin main
   ```
2. **Vercel**:
   - Войди в [vercel.com](https://vercel.com/) и выбери проект `Digital-Scout`.
   - Если проект уже подключен к GitHub-репозиторию, Vercel автоматически запустит новую сборку при push в `main`.
   - Если деплоишь впервые: нажми **Add New → Project**, выбери репозиторий `Digital-Scout` и нажми **Deploy**.
3. **Как устроена конфигурация Vercel**:
   - `api/index.py` — стандартная точка входа Vercel Serverless Function, экспортирует ASGI-приложение `app` из `main.py`.
   - `vercel.json` — маршрутизирует все входящие запросы в `api/index.py` и включает папку `static/**` в сборку функции.
   - `static/` — статические файлы интерфейса (`index.html`, `style.css`, `app.js`).

---

## Запуск локально в Windows

1. Открой терминал в папке проекта.
2. Установи зависимости:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Запусти сервер разработки:
   ```powershell
   python -m uvicorn main:app --reload
   ```
4. Открой в браузере: [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## API эндпоинты

- `GET /api/health` — проверка работоспособности сервера и список источников.
- `GET /api/search?q=Spotify%20Premium` — поиск предложений по всем площадкам.
- Дополнительный параметр `source`:
  - `all` (по умолчанию)
  - `Plati.Market`
  - `GGsel`
  - `FunPay`
  - `Playerok`

Формат ответа:
```json
{
  "query": "Spotify Premium",
  "count": 49,
  "mode": "live-search",
  "notice": "Живые объявления загружены...",
  "providers": [
    {"source": "Plati.Market", "status": "live", "count": 24},
    {"source": "FunPay", "status": "live", "count": 25},
    {"source": "GGsel", "status": "live", "count": 0},
    {"source": "Playerok", "status": "cloudflare-protected", "count": 0}
  ],
  "offers": [
    {
      "title": "🟢 SPOTIFY PREMIUM 1-12 МЕСЯЦЕВ...",
      "price": 139.0,
      "source": "Plati.Market",
      "url": "https://plati.market/itm/..."
    }
  ]
}
```

---

## Структура проекта

```text
├── api/
│   └── index.py        # Точка входа для Vercel Serverless Function
├── static/
│   ├── index.html      # Главная страница
│   ├── style.css       # Стили интерфейса
│   └── app.js          # Логика поиска и отображения карточек
├── main.py             # FastAPI сервер, адаптеры площадок, сортировка
├── requirements.txt    # Зависимости Python
├── vercel.json         # Конфигурация Vercel rewrites & functions
└── README.md           # Документация проекта
```

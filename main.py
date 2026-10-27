
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="DigitalScout", version="0.1.0")

# CSS и JavaScript находятся в корне проекта,
# поэтому отдельная папка static не требуется.
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR)),
    name="static"
)

DEMO_OFFERS = [
    {
        "title": "Windows 11 Pro — цифровой ключ",
        "price": 1290,
        "currency": "RUB",
        "source": "Plati.Market",
        "seller": "Демо-продавец",
        "rating": None,
        "region": "Уточнить регион",
        "kind": "Ключ",
        "url": "https://plati.market/"
    },
    {
        "title": "Windows 11 Pro — ключ активации",
        "price": 1450,
        "currency": "RUB",
        "source": "GGsel",
        "seller": "Демо-продавец",
        "rating": None,
        "region": "Уточнить регион",
        "kind": "Ключ",
        "url": "https://ggsel.net/"
    },
    {
        "title": "Windows 11 Pro — цифровая версия",
        "price": 1590,
        "currency": "RUB",
        "source": "FunPay",
        "seller": "Демо-продавец",
        "rating": None,
        "region": "Уточнить регион",
        "kind": "Ключ",
        "url": "https://funpay.com/"
    },
    {
        "title": "Spotify Premium — подписка",
        "price": 399,
        "currency": "RUB",
        "source": "Plati.Market",
        "seller": "Демо-продавец",
        "rating": None,
        "region": "Проверить условия",
        "kind": "Подписка",
        "url": "https://plati.market/"
    },
    {
        "title": "Spotify Premium — цифровая услуга",
        "price": 450,
        "currency": "RUB",
        "source": "GGsel",
        "seller": "Демо-продавец",
        "rating": None,
        "region": "Проверить условия",
        "kind": "Подписка",
        "url": "https://ggsel.net/"
    }
]

SEARCH_URLS = {
    "Plati.Market": lambda q: (
        "https://plati.market/search/" + quote_plus(q)
    ),
    "GGsel": lambda q: "https://ggsel.net/",
    "FunPay": lambda q: "https://funpay.com/"
}


@app.get("/", response_class=HTMLResponse)
def index():
    file_path = BASE_DIR / "index.html"

    if not file_path.is_file():
        return HTMLResponse(
            "<h1>DigitalScout</h1><p>Файл index.html не найден.</p>",
            status_code=500
        )

    return file_path.read_text(encoding="utf-8")


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, max_length=120),
    source: str = "all",
    max_price: float | None = Query(default=None, ge=0)
):
    query = q.strip().casefold()

    offers = [
        dict(item)
        for item in DEMO_OFFERS
        if query in item["title"].casefold()
    ]

    if source.casefold() != "all":
        offers = [
            item for item in offers
            if item["source"].casefold() == source.casefold()
        ]

    if max_price is not None:
        offers = [
            item for item in offers
            if item["price"] <= max_price
        ]

    offers.sort(key=lambda item: item["price"])

    return {
        "query": q,
        "count": len(offers),
        "mode": "demo",
        "notice": (
            "Демонстрационные цены. "
            "Реальные предложения пока не подключены."
        ),
        "offers": offers,
        "marketplace_searches": [
            {"source": name, "url": builder(q)}
            for name, builder in SEARCH_URLS.items()
            if source.casefold() == "all"
            or source.casefold() == name.casefold()
        ]
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

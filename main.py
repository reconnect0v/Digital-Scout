from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="DigitalScout")
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    path = STATIC_DIR / "index.html"
    if not path.exists():
        return HTMLResponse("static/index.html not found", status_code=500)
    return FileResponse(path)


@app.get("/api/health")
def health():
    return {"status": "ok"}


DEMO_OFFERS = [
    {
        "title": "Windows 11 Pro — цифровой ключ",
        "price": 1290,
        "source": "Plati.Market",
        "url": "https://plati.market/"
    },
    {
        "title": "Windows 11 Pro — ключ активации",
        "price": 1450,
        "source": "GGsel",
        "url": "https://ggsel.net/"
    },
    {
        "title": "Windows 11 Pro — цифровая версия",
        "price": 1590,
        "source": "FunPay",
        "url": "https://funpay.com/"
    }
]


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, max_length=120),
    source: str = "all",
    max_price: float | None = Query(default=None, ge=0)
):
    query = q.strip().casefold()

    offers = [
        item.copy() for item in DEMO_OFFERS
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
        "notice": "Демонстрационные данные, не реальные цены.",
        "offers": offers
    }

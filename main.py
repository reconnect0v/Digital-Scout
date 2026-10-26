from pathlib import Path
from urllib.parse import quote_plus
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="DigitalScout", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# MVP: demo data makes the interface usable before real source adapters are connected.
# Do not treat demo prices as live marketplace offers.
DEMO_OFFERS = [
    {"title": "Windows 11 Pro — цифровой ключ", "price": 1290, "currency": "RUB", "source": "Plati.Market", "seller": "Демо-продавец", "rating": None, "region": "Уточнить регион", "kind": "Ключ", "url": "https://plati.market/"},
    {"title": "Windows 11 Pro — ключ активации", "price": 1450, "currency": "RUB", "source": "GGsel", "seller": "Демо-продавец", "rating": None, "region": "Уточнить регион", "kind": "Ключ", "url": "https://ggsel.net/"},
    {"title": "Windows 11 Pro — цифровая версия", "price": 1590, "currency": "RUB", "source": "FunPay", "seller": "Демо-продавец", "rating": None, "region": "Уточнить регион", "kind": "Ключ", "url": "https://funpay.com/"},
    {"title": "Spotify Premium — подписка", "price": 399, "currency": "RUB", "source": "Plati.Market", "seller": "Демо-продавец", "rating": None, "region": "Проверить срок и способ активации", "kind": "Подписка", "url": "https://plati.market/"},
    {"title": "Spotify Premium — цифровая услуга", "price": 450, "currency": "RUB", "source": "GGsel", "seller": "Демо-продавец", "rating": None, "region": "Проверить срок и способ активации", "kind": "Подписка", "url": "https://ggsel.net/"},
]

SEARCH_URLS = {
    "Plati.Market": lambda q: "https://plati.market/search/" + quote_plus(q),
    "GGsel": lambda q: "https://ggsel.net/" ,
    "FunPay": lambda q: "https://funpay.com/",
}

def get_offers(q: str, source: str = "all", max_price: float | None = None):
    query = q.strip().casefold()
    offers = [dict(o) for o in DEMO_OFFERS if query in o["title"].casefold()]
    if source != "all":
        offers = [o for o in offers if o["source"].casefold() == source.casefold()]
    if max_price is not None:
        offers = [o for o in offers if o["price"] <= max_price]
    offers.sort(key=lambda item: item["price"])
    return offers

@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, max_length=120),
    source: str = "all",
    max_price: float | None = Query(default=None, ge=0),
):
    offers = get_offers(q, source, max_price)
    return {
        "query": q,
        "count": len(offers),
        "mode": "demo",
        "notice": "Это демонстрационные данные, а не актуальные предложения площадок.",
        "offers": offers,
        "marketplace_searches": [
            {"source": name, "url": builder(q)}
            for name, builder in SEARCH_URLS.items()
            if source == "all" or source.casefold() == name.casefold()
        ],
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

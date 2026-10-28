from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import asyncio
import json

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


MARKETPLACES = {
    "Playerok": "playerok.com",
    "FunPay": "funpay.com",
    "Plati.Market": "plati.market",
    "GGsel": "ggsel.net",
}


def search_plati(query: str) -> list[dict]:
    """Read current listings from Plati's documented public catalog search."""
    params = urlencode({
        "query": query,
        "pagesize": 20,
        "pagenum": 1,
        "response": "json",
    })
    request = Request(
        f"https://plati.io/api/search.ashx?{params}",
        headers={"User-Agent": "DigitalScout/0.1"},
    )
    with urlopen(request, timeout=7) as response:
        payload = json.loads(response.read().decode("utf-8"))

    offers = []
    for item in payload.get("items", []):
        try:
            price = float(item["price_rur"])
            title = str(item["name"]).strip()
            url = str(item["url"])
        except (KeyError, TypeError, ValueError):
            continue
        if not title or not url.startswith("https://plati.market/itm/"):
            continue
        offers.append({
            "title": title,
            "price": price,
            "source": "Plati.Market",
            "url": url,
        })
    return offers


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1, max_length=120),
    source: str = "all",
):
    query = q.strip()
    selected = [
        (name, domain) for name, domain in MARKETPLACES.items()
        if source.casefold() == "all" or source.casefold() == name.casefold()
    ]
    providers = []
    offers = []
    for name, domain in selected:
        if name == "Plati.Market" and len(query) >= 3:
            try:
                offers = await asyncio.to_thread(search_plati, query)
                providers.append({"source": name, "status": "live", "count": len(offers)})
                continue
            except Exception:
                providers.append({
                    "source": name,
                    "status": "unavailable",
                    "url": "https://www.google.com/search?" + urlencode({"q": f"site:{domain} {query}"}),
                })
                continue
        providers.append({
            "source": name,
            "status": "external-search",
            "url": "https://www.google.com/search?" + urlencode({"q": f"site:{domain} {query}"}),
        })

    if any(provider["status"] == "live" for provider in providers):
        notice = "Ниже — реальные объявления Plati.Market. Для Playerok, FunPay и GGsel откроется внешний поиск."
    elif any(provider["source"] == "Plati.Market" and provider["status"] == "unavailable" for provider in providers):
        notice = "Не удалось загрузить Plati.Market сейчас. Открой внешний поиск по площадке; проверь цену и наличие на сайте."
    else:
        notice = "Для выбранных площадок откроется внешний поиск. Цены и наличие проверяй на самих сайтах."

    return {
        "query": query,
        "count": len(offers),
        "mode": "live-and-external-search",
        "notice": notice,
        "providers": providers,
        "offers": offers,
    }

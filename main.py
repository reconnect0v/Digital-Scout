from pathlib import Path
from urllib.parse import urlencode
import asyncio
import re

import requests
from bs4 import BeautifulSoup

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


def matches_query(query: str, title: str) -> bool:
    words = re.findall(r"[a-zа-яё0-9]+", query.casefold())
    normalized_title = title.casefold()
    return all(word in normalized_title for word in words)


def search_plati(query: str) -> list[dict]:
    """Read current listings from Plati's documented public catalog search."""
    params = urlencode({
        "query": query,
        "pagesize": 20,
        "pagenum": 1,
        "response": "json",
    })
    response = requests.get(
        f"https://plati.io/api/search.ashx?{params}",
        headers={"User-Agent": "Mozilla/5.0 (compatible; DigitalScout/0.1)"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    offers = []
    for item in payload.get("items", []):
        try:
            price = float(item["price_rur"])
            title = str(item["name"]).strip()
            url = str(item["url"])
        except (KeyError, TypeError, ValueError):
            continue
        if not title or not matches_query(query, title) or not url.startswith("https://plati.market/itm/"):
            continue
        offers.append({
            "title": title,
            "price": price,
            "source": "Plati.Market",
            "url": url,
        })
    return offers


def search_ggsel(query: str) -> list[dict]:
    response = requests.get(
        "https://ggsel.net/catalog",
        params={"search": query},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36"},
        timeout=10,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    offers = []

    for card in soup.select('[data-testid="card"]'):
        title_node = card.select_one('[data-testid="seo-text"]')
        price_node = card.select_one('[data-test="price"]')
        link_node = card.select_one('a[data-testid="card-link"]')
        if not title_node or not price_node or not link_node:
            continue

        price_text = price_node.get_text(" ", strip=True).replace("\u00a0", " ")
        match = re.search(r"([\d ]+(?:[,.]\d+)?)\s*₽", price_text)
        if not match:
            continue
        price = float(match.group(1).replace(" ", "").replace(",", "."))
        title = title_node.get_text(" ", strip=True)
        href = link_node.get("href", "")
        if not title or not matches_query(query, title) or not href.startswith("/catalog/product/"):
            continue
        offers.append({
            "title": title,
            "price": price,
            "source": "GGsel",
            "url": f"https://ggsel.net{href}",
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
    adapters = {
        "Plati.Market": search_plati,
        "GGsel": search_ggsel,
    }
    connected = [(name, adapters[name]) for name, _ in selected if name in adapters]
    results = await asyncio.gather(
        *(asyncio.to_thread(adapter, query) for _, adapter in connected),
        return_exceptions=True,
    )
    offers = []
    provider_results = {}
    for (name, _), result in zip(connected, results):
        if isinstance(result, Exception):
            provider_results[name] = {"source": name, "status": "unavailable", "count": 0}
            continue
        offers.extend(result)
        provider_results[name] = {"source": name, "status": "live", "count": len(result)}

    providers = []
    for name, _ in selected:
        if name in provider_results:
            providers.append(provider_results[name])
        else:
            providers.append({
                "source": name,
                "status": "not-connected",
                "count": 0,
            })
    offers.sort(key=lambda offer: offer["price"])

    live_sources = [provider["source"] for provider in providers if provider["status"] == "live"]
    unavailable_sources = [provider["source"] for provider in providers if provider["status"] != "live"]
    if live_sources and unavailable_sources:
        notice = f"Живые объявления загружены: {', '.join(live_sources)}. Нет прямой выдачи: {', '.join(unavailable_sources)}."
    elif live_sources:
        notice = f"Живые объявления загружены: {', '.join(live_sources)}. Результаты отсортированы по цене."
    else:
        notice = "Не удалось получить живые объявления с выбранных площадок. Попробуй ещё раз позже."

    return {
        "query": query,
        "count": len(offers),
        "mode": "live-search",
        "notice": notice,
        "providers": providers,
        "offers": offers,
    }

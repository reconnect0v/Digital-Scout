import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="DigitalScout", redirect_slashes=False)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_index_path() -> Path:
    candidates = [
        BASE_DIR / "index.html",
        STATIC_DIR / "index.html",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


@app.get("/")
@app.get("/index")
@app.get("/index.html")
@app.get("/api")
@app.get("/api/")
@app.get("/api/index")
@app.get("/api/index.py")
def index():
    path = get_index_path()
    if not path.exists():
        return HTMLResponse("index.html not found", status_code=500)
    return FileResponse(path)


@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "sources": ["Plati.Market", "FunPay", "GGsel", "Playerok"],
    }


MARKETPLACES = {
    "Plati.Market": "plati.market",
    "FunPay": "funpay.com",
    "GGsel": "ggsel.net",
    "Playerok": "playerok.com",
}

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def matches_query(query: str, title: str) -> bool:
    """Check if title contains key terms from the query."""
    words = re.findall(r"[a-zа-яё0-9]+", query.casefold())
    if not words:
        return True
    normalized_title = title.casefold()
    # If single word, must match
    if len(words) == 1:
        return words[0] in normalized_title
    # If multi-word, at least the primary keyword (first word or longest word) must be in title
    primary_word = max(words, key=len)
    return primary_word in normalized_title


# --- Plati.Market Adapter ---
def search_plati(query: str) -> list[dict]:
    """Search listings via Plati's public catalog API."""
    params = urlencode({
        "query": query,
        "pagesize": 25,
        "pagenum": 1,
        "response": "json",
    })
    urls = [
        f"https://plati.market/api/search.ashx?{params}",
        f"https://plati.io/api/search.ashx?{params}",
    ]
    last_error = None

    for url in urls:
        try:
            response = requests.get(
                url,
                headers=COMMON_HEADERS,
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            offers = []
            for item in payload.get("items", []):
                try:
                    price = float(item["price_rur"])
                    title = str(item["name"]).strip()
                    item_url = str(item["url"])
                    if not title or price <= 0:
                        continue
                    if not matches_query(query, title):
                        continue
                    offers.append({
                        "title": title,
                        "price": price,
                        "source": "Plati.Market",
                        "url": item_url,
                    })
                except Exception:
                    continue
            return offers
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Plati.Market недоступен ({last_error})")


# --- FunPay Adapter ---
def search_funpay(query: str) -> list[dict]:
    """Search listings via FunPay promoFilter and category lots pages."""
    filter_headers = dict(COMMON_HEADERS)
    filter_headers["X-Requested-With"] = "XMLHttpRequest"
    filter_headers["Accept"] = "application/json, text/javascript, */*; q=0.01"

    cookies = {
        "cy": "rub",
        "locale": "ru",
    }

    try:
        response = requests.post(
            "https://funpay.com/games/promoFilter",
            data={"query": query},
            headers=filter_headers,
            cookies=cookies,
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        html = data.get("html", "")
    except Exception:
        html = ""

    soup = BeautifulSoup(html, "html.parser")
    games = soup.select(".promo-game-item")

    # If full query returned no games, try searching by individual words
    if not games:
        words = re.findall(r"[a-zа-яё0-9]+", query)
        for word in words:
            if len(word) >= 3:
                try:
                    resp = requests.post(
                        "https://funpay.com/games/promoFilter",
                        data={"query": word},
                        headers=filter_headers,
                        cookies=cookies,
                        timeout=6,
                    )
                    resp.raise_for_status()
                    sub_data = resp.json()
                    sub_soup = BeautifulSoup(sub_data.get("html", ""), "html.parser")
                    games = sub_soup.select(".promo-game-item")
                    if games:
                        break
                except Exception:
                    continue

    if not games:
        return []

    query_words = set(re.findall(r"[a-zа-яё0-9]+", query.casefold()))
    target_categories = []

    for game in games[:2]:
        title_el = game.select_one(".game-title, .promo-game-title")
        game_title = title_el.get_text(strip=True) if title_el else ""

        links = game.select("ul a")
        matched = []
        others = []
        for a in links:
            cat_name = a.get_text(strip=True)
            href = a.get("href")
            if not href:
                continue
            cat_words = set(re.findall(r"[a-zа-яё0-9]+", cat_name.casefold()))
            if query_words & cat_words:
                matched.append((cat_name, href, game_title))
            else:
                others.append((cat_name, href, game_title))

        if matched:
            target_categories.extend(matched[:2])
        elif others:
            target_categories.extend(others[:2])

    offers = []
    # Visit up to 2 targeted lot categories
    for cat_name, cat_url, game_title in target_categories[:2]:
        try:
            resp = requests.get(
                cat_url,
                headers=COMMON_HEADERS,
                cookies=cookies,
                timeout=8,
            )
            resp.raise_for_status()
        except Exception:
            continue

        cat_soup = BeautifulSoup(resp.text, "html.parser")
        items = cat_soup.select("a.tc-item")

        for item in items:
            desc_node = item.select_one(".tc-desc-text") or item.select_one(".tc-desc")
            server_node = item.select_one(".tc-server")
            price_node = item.select_one(".tc-price")
            href = item.get("href", "")

            if not desc_node or not price_node or not href:
                continue

            desc_text = desc_node.get_text(" ", strip=True)
            server_text = server_node.get_text(" ", strip=True) if server_node else ""
            full_title = f"{game_title} — {cat_name}: {server_text} {desc_text}".replace("  ", " ").strip()

            price_text = price_node.get_text(" ", strip=True).replace("\u00a0", " ")
            match = re.search(r"([\d\s]+(?:[.,]\d+)?)\s*₽", price_text)
            if not match:
                continue
            try:
                price = float(match.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                continue

            full_url = href if href.startswith("http") else f"https://funpay.com{href}"
            offers.append({
                "title": full_title,
                "price": price,
                "source": "FunPay",
                "url": full_url,
            })
            if len(offers) >= 30:
                break
        if len(offers) >= 30:
            break

    return offers


# --- GGsel Adapter ---
def search_ggsel(query: str) -> list[dict]:
    """Search listings via GGsel catalog search."""
    urls = ["https://ggsel.net/catalog", "https://ggsel.com/catalog"]
    last_error = None

    for url in urls:
        try:
            response = requests.get(
                url,
                params={"search": query},
                headers=COMMON_HEADERS,
                timeout=8,
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
                try:
                    price = float(match.group(1).replace(" ", "").replace(",", "."))
                except ValueError:
                    continue

                title = title_node.get_text(" ", strip=True)
                href = link_node.get("href", "")
                if not title or not href.startswith("/catalog/product/"):
                    continue
                if not matches_query(query, title):
                    continue

                base_url = "https://ggsel.net" if "ggsel.net" in url else "https://ggsel.com"
                offers.append({
                    "title": title,
                    "price": price,
                    "source": "GGsel",
                    "url": f"{base_url}{href}",
                })
            return offers
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"GGsel недоступен ({last_error})")


# --- Playerok Adapter ---
def search_playerok(query: str) -> list[dict]:
    """Search listings from Playerok.
    Playerok uses Cloudflare Turnstile protection and GraphQL.
    If session cookies (PLAYEROK_COOKIE) are configured, executes an authorized GraphQL query.
    Otherwise attempts public endpoint with TLS impersonation or raises an informative error.
    """
    cookie = os.environ.get("PLAYEROK_COOKIE", "")
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": COMMON_HEADERS["User-Agent"],
        "Origin": "https://playerok.com",
        "Referer": "https://playerok.com/",
    }
    if cookie:
        headers["Cookie"] = cookie

    payload = {
        "operationName": "SearchProducts",
        "variables": {
            "query": query,
            "limit": 20,
        },
        "query": """
        query SearchProducts($query: String!, $limit: Int) {
          searchProducts(query: $query, limit: $limit) {
            id
            title
            name
            price
            slug
          }
        }
        """,
    }

    client = cffi_requests if cffi_requests is not None else requests
    kwargs = {
        "headers": headers,
        "json": payload,
        "timeout": 8,
    }
    if cffi_requests is not None and client == cffi_requests:
        kwargs["impersonate"] = "chrome131"

    url = "https://www.playerok.com/graphql"
    try:
        response = client.post(url, **kwargs)
        if response.status_code in (401, 403):
            raise PermissionError("Cloudflare Turnstile: требуется активная сессия PLAYEROK_COOKIE")
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"Playerok недоступен ({exc})") from exc

    offers = []
    items = (data.get("data") or {}).get("searchProducts") or []
    for item in items:
        try:
            title = item.get("title") or item.get("name") or ""
            price = float(item.get("price") or 0)
            slug = item.get("slug") or str(item.get("id"))
            if not title or price <= 0:
                continue
            offers.append({
                "title": title,
                "price": price,
                "source": "Playerok",
                "url": f"https://playerok.com/products/{slug}",
            })
        except Exception:
            continue

    return offers


@app.get("/api/search")
@app.get("/search")
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
        "FunPay": search_funpay,
        "GGsel": search_ggsel,
        "Playerok": search_playerok,
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
            err_msg = str(result)
            if "Cloudflare" in err_msg or "PLAYEROK_COOKIE" in err_msg:
                status_code = "cloudflare-protected"
            else:
                status_code = "unavailable"
            provider_results[name] = {
                "source": name,
                "status": status_code,
                "count": 0,
                "error": err_msg,
            }
            continue

        offers.extend(result)
        provider_results[name] = {
            "source": name,
            "status": "live",
            "count": len(result),
        }

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

    # Strict sorting from cheapest to most expensive (lowest price first)
    offers.sort(key=lambda item: item["price"])

    live_sources = [p["source"] for p in providers if p["status"] == "live"]
    unavailable_sources = [p["source"] for p in providers if p["status"] != "live"]

    if live_sources and unavailable_sources:
        notice = f"Живые объявления получены: {', '.join(live_sources)}. Не ответили или требуют доступ: {', '.join(unavailable_sources)}."
    elif live_sources:
        notice = f"Живые объявления получены со всех площадок: {', '.join(live_sources)}."
    else:
        notice = "Не удалось получить живые предложения с выбранных площадок. Попробуй ещё раз позже."

    min_price = offers[0]["price"] if offers else 0

    return {
        "query": query,
        "count": len(offers),
        "min_price": min_price,
        "mode": "live-search",
        "notice": notice,
        "providers": providers,
        "offers": offers,
    }


# Catch-all fallback route: handles any request shape forwarded by Vercel rewrites
@app.api_route("/{full_path:path}", methods=["GET", "POST"])
async def catch_all_route(full_path: str, request: Request):
    clean_path = full_path.strip("/")
    # If looking for search
    if clean_path.endswith("search"):
        q = request.query_params.get("q", "")
        source = request.query_params.get("source", "all")
        if q:
            return await search(q=q, source=source)
        return JSONResponse({"error": "missing query"}, status_code=400)

    # If looking for health
    if clean_path.endswith("health"):
        return health()

    # If looking for static file
    if clean_path.startswith("static/"):
        rel_path = clean_path[len("static/"):]
        target = STATIC_DIR / rel_path
        if target.is_file():
            return FileResponse(target)

    # Otherwise return index.html
    path = get_index_path()
    if path.is_file():
        return FileResponse(path)

    return HTMLResponse("index.html not found", status_code=404)

const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const sourceSelect = document.querySelector("#source");
const results = document.querySelector("#results");
const resultsTitle = document.querySelector("#results-title");
const resultCount = document.querySelector("#result-count");
const notice = document.querySelector("#notice");

async function searchOffers() {
  const query = queryInput.value.trim();
  if (!query) return;

  results.className = "results empty";
  results.textContent = "Готовим поиск по площадкам…";
  resultsTitle.textContent = `Поиск: ${query}`;
  resultCount.textContent = "";

  const params = new URLSearchParams({ q: query, source: sourceSelect.value });

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    if (!response.ok) throw new Error(`Ошибка сервера (${response.status})`);

    const data = await response.json();
    notice.textContent = data.notice;
    const inactiveProviders = data.providers.filter((item) => item.status !== "live");
    const countParts = [];
    if (data.offers.length) countParts.push(`${data.offers.length} объявлений`);
    if (inactiveProviders.length) countParts.push(`${inactiveProviders.length} с ограничениями`);
    resultCount.textContent = countParts.join(" · ");
    results.replaceChildren();
    results.className = "results provider-results";

    if (!data.offers.length && !inactiveProviders.length) {
      results.className = "results empty";
      results.textContent = "По этому запросу нет результатов.";
      return;
    }

    for (const offer of data.offers) {
      const card = document.createElement("article");
      card.className = "offer";

      const details = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = offer.title;
      const meta = document.createElement("div");
      meta.className = "offer-meta";
      const source = document.createElement("span");
      source.className = "tag";
      source.textContent = offer.source;
      meta.append(source);
      details.append(title, meta);

      const price = document.createElement("div");
      price.className = "price";
      price.textContent = `${offer.price.toLocaleString("ru-RU")} ₽`;

      const link = document.createElement("a");
      link.className = "open-link";
      link.href = offer.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Открыть объявление →";

      card.append(details, price, link);
      results.append(card);
    }

    for (const provider of inactiveProviders) {
      const card = document.createElement("article");
      card.className = "provider-search-card";

      const name = document.createElement("div");
      name.className = "provider-search-name";
      name.textContent = provider.source;

      const description = document.createElement("p");
      if (provider.status === "cloudflare-protected") {
        description.textContent = "Защита Cloudflare Turnstile: для прямого поиска по Playerok требуется активная браузерная сессия (PLAYEROK_COOKIE).";
      } else if (provider.status === "unavailable") {
        description.textContent = "Площадка временно не ответила на запрос.";
      } else {
        description.textContent = "Прямой источник для этой площадки временно недоступен.";
      }

      card.append(name, description);
      results.append(card);
    }
  } catch (error) {
    results.className = "results empty";
    results.textContent = `Не удалось выполнить поиск. ${error.message}`;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  searchOffers();
});

sourceSelect.addEventListener("change", () => {
  if (queryInput.value.trim()) searchOffers();
});

document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.query;
    searchOffers();
  });
});

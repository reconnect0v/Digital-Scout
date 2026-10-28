const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const sourceSelect = document.querySelector("#source");
const maxPriceInput = document.querySelector("#max-price");
const applyFiltersButton = document.querySelector("#apply-filters");
const results = document.querySelector("#results");
const resultsTitle = document.querySelector("#results-title");
const resultCount = document.querySelector("#result-count");

async function searchOffers() {
  const query = queryInput.value.trim();
  if (!query) return;

  results.className = "results empty";
  results.replaceChildren(document.createTextNode("Ищем предложения…"));
  resultsTitle.textContent = `Результаты: ${query}`;
  resultCount.textContent = "";

  const params = new URLSearchParams({ q: query, source: sourceSelect.value });
  const maxPrice = maxPriceInput.value.trim();
  if (maxPrice) params.set("max_price", maxPrice);

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    if (!response.ok) throw new Error(`Ошибка сервера (${response.status})`);

    const data = await response.json();
    resultCount.textContent = `${data.count} предложений`;
    results.replaceChildren();

    if (!data.offers.length) {
      results.className = "results empty";
      results.textContent = "По этому запросу предложений не найдено.";
      return;
    }

    results.className = "results";
    for (const offer of data.offers) {
      const card = document.createElement("article");
      card.className = "offer";

      const details = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = offer.title;
      const meta = document.createElement("div");
      meta.className = "offer-meta";
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = offer.source;
      meta.append(tag);
      details.append(title, meta);

      const price = document.createElement("div");
      price.className = "price";
      price.textContent = `${offer.price.toLocaleString("ru-RU")} ₽`;

      const link = document.createElement("a");
      link.className = "open-link";
      link.href = offer.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Открыть площадку →";

      card.append(details, price, link);
      results.append(card);
    }
  } catch (error) {
    results.className = "results empty";
    results.textContent = `Не удалось загрузить предложения. ${error.message}`;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  searchOffers();
});

applyFiltersButton.addEventListener("click", searchOffers);

document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.query;
    searchOffers();
  });
});

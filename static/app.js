const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const searchButton = document.querySelector("#search-button");
const resultsSection = document.querySelector("#results-section");
const resultsGrid = document.querySelector("#results");
const resultsTitle = document.querySelector("#results-title");
const statsPill = document.querySelector("#stats-pill");
const noticeBox = document.querySelector("#notice");

const sortSelect = document.querySelector("#sort-order");
const minPriceInput = document.querySelector("#min-price");
const maxPriceInput = document.querySelector("#max-price");
const platformPills = document.querySelectorAll(".platform-pill");

let currentOffers = [];
let currentProviders = [];
let selectedPlatform = "all";

function scrollToResults() {
  if (resultsSection) {
    const yOffset = -80; // Offset for sticky topbar
    const y = resultsSection.getBoundingClientRect().top + window.pageYOffset + yOffset;
    window.scrollTo({ top: y, behavior: "smooth" });
  }
}

function renderSkeletons() {
  resultsGrid.innerHTML = "";
  for (let i = 0; i < 6; i++) {
    const card = document.createElement("div");
    card.className = "skeleton-card";
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div class="skeleton-shimmer" style="width: 80px; height: 24px;"></div>
        <div class="skeleton-shimmer" style="width: 90px; height: 28px;"></div>
      </div>
      <div class="skeleton-shimmer" style="width: 100%; height: 42px; margin: 12px 0;"></div>
      <div class="skeleton-shimmer" style="width: 100%; height: 38px;"></div>
    `;
    resultsGrid.appendChild(card);
  }
}

function updatePlatformCounters() {
  const counts = {
    all: currentOffers.length,
    "FunPay": 0,
    "Plati.Market": 0,
    "GGsel": 0,
    "Playerok": 0,
  };

  for (const offer of currentOffers) {
    if (counts[offer.source] !== undefined) {
      counts[offer.source]++;
    }
  }

  const elAll = document.querySelector("#count-all");
  const elFunPay = document.querySelector("#count-funpay");
  const elPlati = document.querySelector("#count-plati");
  const elGGsel = document.querySelector("#count-ggsel");
  const elPlayerok = document.querySelector("#count-playerok");

  if (elAll) elAll.textContent = counts.all;
  if (elFunPay) elFunPay.textContent = counts["FunPay"];
  if (elPlati) elPlati.textContent = counts["Plati.Market"];
  if (elGGsel) elGGsel.textContent = counts["GGsel"];
  if (elPlayerok) elPlayerok.textContent = counts["Playerok"];
}

function applyFiltersAndRender() {
  let filtered = [...currentOffers];

  // 1. Platform filter
  if (selectedPlatform !== "all") {
    filtered = filtered.filter(
      (o) => o.source.toLowerCase() === selectedPlatform.toLowerCase()
    );
  }

  // 2. Price range filter
  const minVal = parseFloat(minPriceInput.value);
  const maxVal = parseFloat(maxPriceInput.value);

  if (!isNaN(minVal) && minVal >= 0) {
    filtered = filtered.filter((o) => o.price >= minVal);
  }
  if (!isNaN(maxVal) && maxVal > 0) {
    filtered = filtered.filter((o) => o.price <= maxVal);
  }

  // 3. Sorting (Default: cheap first)
  const sortOrder = sortSelect.value;
  if (sortOrder === "cheap-first") {
    filtered.sort((a, b) => a.price - b.price);
  } else if (sortOrder === "expensive-first") {
    filtered.sort((a, b) => b.price - a.price);
  }

  // Render cards
  resultsGrid.innerHTML = "";

  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <div class="empty-icon">✕</div>
      <h3>Нет подходящих предложений</h3>
      <p>Попробуй сбросить фильтр площадки или расширить диапазон цен.</p>
    `;
    resultsGrid.appendChild(empty);
  } else {
    for (const offer of filtered) {
      const card = document.createElement("article");
      card.className = "offer-card";

      const sourceClass = offer.source.toLowerCase().replace(/[^a-z]/g, "");

      card.innerHTML = `
        <div class="card-top">
          <span class="tag-badge ${sourceClass}">
            ● ${offer.source}
          </span>
          <div class="card-price">
            ${offer.price.toLocaleString("ru-RU")} ₽
          </div>
        </div>

        <div class="card-title" title="${offer.title}">
          ${offer.title}
        </div>

        <a class="card-link" href="${offer.url}" target="_blank" rel="noopener noreferrer">
          Купить на ${offer.source} →
        </a>
      `;

      resultsGrid.appendChild(card);
    }
  }

  // Render inactive provider status cards if looking at all or specific provider
  for (const provider of currentProviders) {
    if (provider.status === "live") continue;
    if (selectedPlatform !== "all" && selectedPlatform.toLowerCase() !== provider.source.toLowerCase()) {
      continue;
    }

    const pCard = document.createElement("div");
    pCard.className = "provider-status-card";
    let desc = "Площадка временно не ответила.";
    if (provider.status === "cloudflare-protected") {
      desc = "Площадка защищена Cloudflare Turnstile. Требуются куки браузерной сессии.";
    }

    pCard.innerHTML = `
      <b>⚠️ ${provider.source}</b>
      <p>${desc}</p>
    `;
    resultsGrid.appendChild(pCard);
  }

  // Update stats pill
  if (currentOffers.length > 0) {
    const minP = Math.min(...currentOffers.map((o) => o.price));
    statsPill.textContent = `⚡ Найдено ${filtered.length} из ${currentOffers.length} предл. (от ${minP.toLocaleString("ru-RU")} ₽)`;
  } else {
    statsPill.textContent = "0 предложений";
  }
}

async function searchOffers() {
  const query = queryInput.value.trim();
  if (!query) return;

  resultsTitle.textContent = `Поиск: ${query}`;
  statsPill.textContent = "Ищем по площадкам…";
  searchButton.disabled = true;
  searchButton.textContent = "Поиск…";

  renderSkeletons();
  scrollToResults();

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&source=all`);
    if (!response.ok) throw new Error(`Ошибка сервера (${response.status})`);

    const data = await response.json();
    currentOffers = data.offers || [];
    currentProviders = data.providers || [];

    if (data.notice) {
      noticeBox.textContent = data.notice;
      noticeBox.style.display = "block";
    } else {
      noticeBox.style.display = "none";
    }

    updatePlatformCounters();
    applyFiltersAndRender();
  } catch (error) {
    noticeBox.style.display = "none";
    statsPill.textContent = "Ошибка поиска";
    resultsGrid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h3>Не удалось выполнить поиск</h3>
        <p>${error.message}. Попробуй обновить страницу или повторить запрос позже.</p>
      </div>
    `;
  } finally {
    searchButton.disabled = false;
    searchButton.textContent = "Найти предложения →";
  }
}

// Event Listeners
form.addEventListener("submit", (e) => {
  e.preventDefault();
  searchOffers();
});

sortSelect.addEventListener("change", applyFiltersAndRender);
minPriceInput.addEventListener("input", applyFiltersAndRender);
maxPriceInput.addEventListener("input", applyFiltersAndRender);

platformPills.forEach((pill) => {
  pill.addEventListener("click", () => {
    platformPills.forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    selectedPlatform = pill.dataset.platform;
    applyFiltersAndRender();
  });
});

document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.query;
    searchOffers();
  });
});

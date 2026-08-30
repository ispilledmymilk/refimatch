const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  catalog: [],
  selected: new Set(),
  overrides: {},
  loading: false,
  market: null,
  listings: [],
  subject: null,
  marketMeta: null,
  appreciation: null,
  compsSummary: null,
  offerSources: null,
};

function renderOffersSource(data) {
  const box = $("#benchmark-box");
  const b = data.market_benchmark;
  if ($("#offers-source")) {
    $("#offers-source").textContent = "Select offers to compare";
  }
  if (b && b.rate_pct != null) {
    box.classList.remove("hidden");
    const chg = b.week_change_pct_points != null
      ? ` · week Δ ${b.week_change_pct_points >= 0 ? "+" : ""}${b.week_change_pct_points.toFixed(2)} pts`
      : "";
    box.innerHTML = `
      <div class="label">Freddie Mac 30-yr national avg</div>
      <div class="value">${Number(b.rate_pct).toFixed(2)}% <span style="font-size:0.75rem;font-weight:500;color:var(--muted)">as of ${b.as_of}${chg}</span></div>
    `;
  } else {
    box.classList.add("hidden");
  }
}

const fmt = {
  money(v) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(v);
  },
  pct(frac) {
    return `${(frac * 100).toFixed(2)}%`;
  },
  pct1(frac) {
    return `${(frac * 100).toFixed(1)}%`;
  },
  breakeven(m) {
    if (m == null || !Number.isFinite(m)) return "Breakeven n/a";
    return `Breakeven ${Math.ceil(m)} mo`;
  },
  dist(listing) {
    if (listing.same_building) return "Same building";
    if (listing.distance_km != null) return `${listing.distance_km.toFixed(1)} km`;
    if (listing.distance_miles) return `${listing.distance_miles} mi`;
    return "";
  },
};

function lenderName(id) {
  const o = state.catalog.find((x) => x.lender_id === id);
  return o ? o.lender_name : id;
}

function shortName(id) {
  const n = lenderName(id);
  return n.length <= 14 ? n : `${n.slice(0, 12)}…`;
}

function normalizedWeights() {
  const a = Math.max(parseFloat($("#w-payment").value) || 0, 0);
  const b = Math.max(parseFloat($("#w-total").value) || 0, 0);
  const c = Math.max(parseFloat($("#w-breakeven").value) || 0, 0);
  const s = a + b + c || 1;
  return {
    monthly_payment: a / s,
    total_cost_horizon: b / s,
    breakeven_months: c / s,
  };
}

function parseScenario() {
  const principal = parseFloat($("#principal").value);
  const ratePct = parseFloat($("#rate").value);
  const termYears = parseFloat($("#term-years").value);
  const monthsPaid = parseInt($("#months-paid").value, 10);
  const holdYears = parseInt($("#hold-years").value, 10);
  if (!principal || !ratePct || !termYears || isNaN(monthsPaid) || !holdYears) {
    throw new Error("Check loan fields — all values must be positive numbers.");
  }
  return {
    original_principal: principal,
    annual_rate: ratePct / 100,
    term_months: Math.round(termYears * 12),
    months_paid: Math.max(0, monthsPaid),
    hold_horizon_months: holdYears * 12,
  };
}

function selectedOffers() {
  return [...state.selected].map((id) => {
    const base = state.catalog.find((o) => o.lender_id === id);
    if (!base) return null;
    const o = state.overrides[id] || base;
    return { ...o };
  }).filter(Boolean);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data;
}

function setLoading(on) {
  state.loading = on;
  const analyze = $("#btn-analyze");
  if (analyze) analyze.disabled = on || state.selected.size === 0;
  const demo = $("#btn-demo");
  if (demo) demo.disabled = on;
  ["#btn-lookup", "#btn-lookup-form"].forEach((sel) => {
    const el = $(sel);
    if (el) el.disabled = on;
  });
  $("#status-loading")?.classList.toggle("hidden", !on);
  $("#comps-loading")?.classList.toggle("hidden", !on);
}

function showError(msg) {
  const el = $("#error");
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}

function showCompsError(msg) {
  const el = $("#comps-error");
  if (!el) return;
  if (msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}

function switchTab(name) {
  $$(".tab").forEach((t) => {
    const on = t.dataset.tab === name;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  $$(".panel").forEach((p) => {
    const on = p.id === `panel-${name}`;
    p.classList.toggle("active", on);
    p.hidden = !on;
  });
  if (name === "comps" && window.location.hash !== "#comps") {
    history.replaceState(null, "", "#comps");
  } else if (name === "refinance" && window.location.hash) {
    history.replaceState(null, "", window.location.pathname);
  }
}

function renderOffers() {
  const root = $("#offers-list");
  if (!root) return;
  root.innerHTML = "";
  if (!state.catalog.length) {
    root.innerHTML = "<p class='muted'>Loading offers…</p>";
    return;
  }
  for (const offer of state.catalog) {
    const id = offer.lender_id;
    const checked = state.selected.has(id);
    const row = document.createElement("div");
    row.className = "offer";
    row.innerHTML = `
      <div class="offer-head">
        <input type="checkbox" id="cb-${id}" ${checked ? "checked" : ""} />
        <div>
          <div class="offer-name">${offer.lender_name}</div>
          <div class="offer-meta">APR ${fmt.pct(offer.apr)} · fees ${fmt.money(offer.lender_fees)}${offer.notes ? ` · ${offer.notes}` : ""}</div>
        </div>
      </div>
      <div class="offer-apr ${checked ? "visible" : ""}" id="apr-${id}">
        <label>Override APR %</label>
        <input type="number" step="0.001" value="${((state.overrides[id]?.apr ?? offer.apr) * 100).toFixed(3)}" />
      </div>
    `;
    root.appendChild(row);

    row.querySelector(`#cb-${id}`).addEventListener("change", (e) => {
      if (e.target.checked) state.selected.add(id);
      else state.selected.delete(id);
      row.querySelector(`#apr-${id}`).classList.toggle("visible", e.target.checked);
      $("#btn-analyze").disabled = state.loading || state.selected.size === 0;
    });

    const aprInput = row.querySelector(`#apr-${id} input`);
    aprInput.addEventListener("change", () => {
      const base = state.catalog.find((o) => o.lender_id === id);
      state.overrides[id] = {
        ...base,
        apr: parseFloat(aprInput.value) / 100,
      };
    });
  }
}

function propertyTypeApiValue() {
  const v = ($("#prop-type")?.value || "detached").trim();
  const allowed = new Set(["apartment", "townhouse", "semi_detached", "detached"]);
  return allowed.has(v) ? v : "detached";
}

function readSubjectFromForm() {
  const street = ($("#prop-street").value || "").trim();
  const city = ($("#prop-city").value || "").trim();
  const st = ($("#prop-state").value || "").trim().toUpperCase();
  const zip = ($("#prop-zip").value || "").trim();
  const purchasePrice = parseFloat($("#purchase-price").value);
  const askingRaw = $("#asking-price").value;
  const asking = askingRaw === "" || askingRaw == null ? null : parseFloat(askingRaw);
  const sqft = parseInt($("#sqft").value, 10);
  const beds = parseInt($("#prop-beds").value, 10);
  const baths = parseFloat($("#prop-baths").value);
  const yearBuilt = parseInt($("#prop-year").value, 10);
  const purchaseDate = $("#purchase-date").value;
  const condition = $("#prop-condition").value || "good";

  if (!street || !city || !st) {
    throw new Error("Enter street, city, and state for your property.");
  }
  if (!purchasePrice || !sqft || !purchaseDate) {
    throw new Error("Purchase price, sqft, and purchase date are required.");
  }

  return {
    property_id: "user-home",
    address: street,
    city,
    state: st,
    zip_code: zip || "00000",
    beds: Number.isFinite(beds) ? beds : 0,
    baths: Number.isFinite(baths) ? baths : 0,
    sqft,
    year_built: yearBuilt || 2000,
    property_type: propertyTypeApiValue(),
    condition,
    purchase_price: purchasePrice,
    purchase_date: purchaseDate,
    asking_price: Number.isFinite(asking) ? asking : null,
  };
}

function fillFormFromSubject(s) {
  if (!s) return;
  $("#prop-street").value = s.address || "";
  $("#prop-city").value = s.city || "";
  $("#prop-state").value = s.state || "";
  $("#prop-zip").value = s.zip_code || "";
  $("#prop-beds").value = s.beds ?? "";
  $("#prop-baths").value = s.baths ?? "";
  $("#sqft").value = s.sqft ?? "";
  $("#prop-year").value = s.year_built ?? "";
  $("#purchase-price").value = s.purchase_price ?? "";
  if (s.purchase_date) $("#purchase-date").value = String(s.purchase_date).slice(0, 10);
  if (s.asking_price != null) $("#asking-price").value = s.asking_price;
  if (s.condition) $("#prop-condition").value = s.condition;
  if (s.property_type) {
    const t = String(s.property_type).toLowerCase().replace(/-/g, "_").replace(/\s+/g, "_");
    if (["apartment", "townhouse", "semi_detached", "detached"].includes(t)) {
      $("#prop-type").value = t;
    } else if (/condo|apartment|apt|flat/.test(t)) {
      $("#prop-type").value = "apartment";
    } else if (/town/.test(t)) {
      $("#prop-type").value = "townhouse";
    } else if (/semi/.test(t)) {
      $("#prop-type").value = "semi_detached";
    } else {
      $("#prop-type").value = "detached";
    }
  }
}

function renderAppreciationResults() {
  const a = state.appreciation;
  const subject = state.subject;
  const summary = state.compsSummary || {};
  if (!a || !subject) return;

  $("#comps-results").classList.remove("hidden");
  $("#estimate-value").textContent = fmt.money(a.estimated_value);
  $("#estimate-headline").textContent = summary.headline || "";

  const pills = [];
  if (summary.subject_vs_median_listing) pills.push(summary.subject_vs_median_listing);
  if (summary.asking_vs_estimate) pills.push(summary.asking_vs_estimate);
  if (state.marketMeta?.sources?.search_radius) {
    pills.push(`Search: ${state.marketMeta.sources.search_radius}`);
  }
  $("#estimate-pills").innerHTML = pills
    .map((t) => `<div class="pill">${t}</div>`)
    .join("");

  const stats = [
    ["Purchase price", fmt.money(a.purchase_price)],
    ["Total appreciation", fmt.money(a.appreciation_dollars)],
    ["Appreciation %", fmt.pct1(a.appreciation_pct)],
    ["Annualized return", fmt.pct1(a.annualized_appreciation_pct)],
    ["Years held", a.years_held.toFixed(1)],
    ["Your $/sqft", `$${Number(state.subjectPricePerSqft || a.estimated_value / subject.sqft).toFixed(0)}`],
    ["Area median $/sqft", `$${Number(state.market?.median_price_per_sqft || 0).toFixed(0)}`],
    ["Area YoY", fmt.pct1(a.yoy_area_appreciation_pct)],
  ];
  $("#appreciation-stats").innerHTML = stats
    .map(([label, value]) => `<div class="stat-box"><div class="label">${label}</div><div class="value">${value}</div></div>`)
    .join("");
}

function renderListingsPreview() {
  const root = $("#listings-list");
  if (!root) return;
  root.innerHTML = "";

  const n = state.listings.length;
  const area = state.market?.area_name || "";
  $("#listings-heading").textContent =
    n > 0 ? `${n} comparable listing${n === 1 ? "" : "s"}${area ? ` in ${area}` : ""}` : "Comparable listings";
  $("#market-area").textContent = state.market
    ? `Median ${fmt.money(state.market.median_list_price)} · ${fmt.pct1(state.market.yoy_appreciation_pct)} YoY area`
    : "";

  if (!n) {
    root.innerHTML = "<p class='muted'>No listings loaded.</p>";
    return;
  }

  const comparisons = Object.fromEntries(
    (state.listingComparisons || []).map((c) => [c.listing_id, c])
  );

  state.listings.forEach((l, i) => {
    const ppsf = l.asking_price / l.sqft;
    const dist = fmt.dist(l);
    const badge = l.same_building ? "Same building" : "For Sale";
    const badgeClass = l.same_building ? "same" : "";
    const img = l.image_url
      ? `<img src="${l.image_url}" alt="" loading="lazy"/>`
      : "";
    const cmp = comparisons[l.listing_id];
    let deltaHtml = "";
    if (cmp) {
      const cls = cmp.vs_subject_price_delta >= 0 ? "negative" : "positive";
      deltaHtml = `<div class="listing-delta ${cls}">${cmp.vs_subject_price_delta >= 0 ? "+" : ""}${fmt.money(cmp.vs_subject_price_delta)} vs estimate</div>`;
    }

    const div = document.createElement("article");
    div.className = "listing-card";
    div.style.animationDelay = `${Math.min(i, 8) * 0.05}s`;
    div.innerHTML = `
      <div class="listing-media">
        ${img}
        <span class="listing-badge ${badgeClass}">${badge}</span>
      </div>
      <div class="listing-body">
        <p class="listing-price">${fmt.money(l.asking_price)}</p>
        <div class="listing-facts">
          <div>${l.beds} <span>bd</span></div>
          <div>${l.baths} <span>ba</span></div>
          <div>${l.sqft.toLocaleString()} <span>sqft</span></div>
          ${dist ? `<div>${dist}</div>` : ""}
        </div>
        <p class="listing-addr">${l.address}${l.city ? `, ${l.city}` : ""} · $${ppsf.toFixed(0)}/sqft</p>
        ${deltaHtml}
      </div>
    `;
    root.appendChild(div);
  });
}

async function lookupMarketFromForm() {
  setLoading(true);
  showCompsError(null);
  showError(null);
  try {
    const subject = readSubjectFromForm();
    const data = await api("/v1/market/lookup", {
      method: "POST",
      body: JSON.stringify({
        subject,
        country: ($("#prop-country")?.value || "").trim() || undefined,
        state: subject.state,
        zip_code: subject.zip_code,
        city: subject.city,
        address: subject.address,
        property_type: subject.property_type,
      }),
    });
    applyMarketPayload(data);
    switchTab("comps");
    $("#comps-results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    showCompsError(e.message);
  } finally {
    setLoading(false);
  }
}

function applyMarketPayload(data) {
  state.market = data.market;
  state.subject = data.subject_property;
  state.listings = data.listings || [];
  state.appreciation = data.appreciation || null;
  state.compsSummary = data.summary || null;
  state.subjectPricePerSqft = data.subject_price_per_sqft;
  state.listingComparisons = data.listing_comparisons || [];
  state.marketMeta = { sources: data.data_sources, fetchedAt: data.fetched_at };
  fillFormFromSubject(state.subject);
  if (data.country || data.data_sources?.country) {
    const c = data.country || data.data_sources.country;
    if ($("#prop-country")) $("#prop-country").value = c;
  }
  if (state.appreciation) {
    renderAppreciationResults();
  } else if (state.subject) {
    // Catalog load without analysis — still show listings
    $("#comps-results")?.classList.add("hidden");
  }
  renderListingsPreview();
  if (state.appreciation) {
    $("#comps-results").classList.remove("hidden");
  }
}

async function loadMarketCatalog() {
  // Soft preload — don't block UI; comps tab loads on demand.
  try {
    const data = await api("/v1/catalog/demo-listings");
    state.market = data.market;
    state.subject = data.subject_property;
    state.listings = data.listings || [];
    state.marketMeta = { sources: data.data_sources, fetchedAt: data.fetched_at };
    fillFormFromSubject(state.subject);
  } catch {
    /* ignore — user can still lookup */
  }
}

function renderResults(compare, explain, headline) {
  $("#results").classList.remove("hidden");
  if (headline) {
    $("#headline").textContent = headline;
    $("#headline-card").classList.remove("hidden");
  } else {
    $("#headline-card").classList.add("hidden");
  }

  const top = compare.ranked_lender_ids[0];
  const m = compare.metrics_by_lender[top];
  if (m) {
    $("#winner-section").classList.remove("hidden");
    $("#winner-name").textContent = lenderName(top);
    $("#winner-pills").innerHTML = `
      <div class="pill"><span>Payment</span>${fmt.money(m.new_monthly_pi)}</div>
      <div class="pill"><span>Breakeven</span>${fmt.breakeven(m.breakeven_months)}</div>
    `;
    $("#winner-baseline").textContent =
      `Current payment baseline: ${fmt.money(compare.baseline_monthly_pi)}/mo · Balance ${fmt.money(compare.current_balance)}`;
  }

  const rankRoot = $("#ranking");
  rankRoot.innerHTML = "";
  compare.ranked_lender_ids.forEach((id, idx) => {
    const met = compare.metrics_by_lender[id];
    if (!met) return;
    const div = document.createElement("div");
    div.className = "rank-row";
    div.innerHTML = `
      <div class="rank-num ${idx === 0 ? "first" : ""}">${idx + 1}</div>
      <div class="rank-detail">
        <div class="name">${lenderName(id)}</div>
        <div>${fmt.money(met.new_monthly_pi)}/mo · closing ${fmt.money(met.closing_costs)}</div>
        <div class="sub">Horizon total ${fmt.money(met.total_cost_horizon)} · ${fmt.breakeven(met.breakeven_months)}</div>
      </div>
    `;
    rankRoot.appendChild(div);
  });

  const maxPay = Math.max(
    ...compare.ranked_lender_ids.map((id) => compare.metrics_by_lender[id]?.new_monthly_pi || 0)
  );
  const chartRoot = $("#chart");
  chartRoot.innerHTML = "";
  for (const id of compare.ranked_lender_ids) {
    const met = compare.metrics_by_lender[id];
    if (!met) continue;
    const pct = maxPay > 0 ? (met.new_monthly_pi / maxPay) * 100 : 0;
    const col = document.createElement("div");
    col.className = "chart-col";
    col.innerHTML = `
      <div class="chart-value">${fmt.money(met.new_monthly_pi)}</div>
      <div class="chart-bar-wrap">
        <div class="chart-bar ${id === top ? "winner" : ""}" style="height:${pct}%"></div>
      </div>
      <div class="chart-label">${shortName(id)}</div>
    `;
    chartRoot.appendChild(col);
  }

  if (explain) {
    $("#explain-text").textContent = explain.explanation;
    const citRoot = $("#citations-list");
    citRoot.innerHTML = "";
    (explain.citations || []).slice(0, 3).forEach((c) => {
      const li = document.createElement("li");
      li.textContent = c.text;
      citRoot.appendChild(li);
    });
    $("#citations").classList.toggle("hidden", !(explain.citations || []).length);
  }
}

async function loadCatalog() {
  try {
    await loadMarketCatalog();
    const data = await api("/v1/catalog/demo-offers");
    state.catalog = data.offers || [];
    renderOffersSource(data);
    state.offerSources = data.data_sources || {};
    if (!state.selected.size) {
      state.catalog.forEach((o) => state.selected.add(o.lender_id));
    }
    renderOffers();
    $("#btn-analyze").disabled = state.selected.size === 0;
  } catch (e) {
    showError(`Could not load offers: ${e.message}`);
  }
}

async function runQuickDemo() {
  setLoading(true);
  showError(null);
  try {
    const data = await api("/v1/demo/run", { method: "POST", body: "{}" });
    renderResults(data.compare, data.explain, data.headline);
    switchTab("refinance");
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
}

async function runFullAnalysis() {
  setLoading(true);
  showError(null);
  try {
    const scenario = parseScenario();
    const offers = selectedOffers();
    if (!offers.length) throw new Error("Select at least one lender offer.");
    const compare = await api("/v1/compare", {
      method: "POST",
      body: JSON.stringify({
        scenario,
        offers,
        weights: normalizedWeights(),
      }),
    });
    const explain = await api("/v1/explain", {
      method: "POST",
      body: JSON.stringify({
        compare_result: compare,
        user_question: "Explain this ranking for a homeowner in plain language.",
      }),
    });
    const top = compare.ranked_lender_ids[0];
    renderResults(compare, explain, top ? `Top pick: ${lenderName(top)}` : null);
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
}

function bindSliders() {
  ["#w-payment", "#w-total", "#w-breakeven"].forEach((sel) => {
    $(sel).addEventListener("input", () => {
      $(`${sel}-val`).textContent = parseFloat($(sel).value).toFixed(2);
    });
  });
}

function bindTabs() {
  $$(".tab, .brand").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const name = el.dataset.tab || "refinance";
      switchTab(name);
    });
  });
  if (window.location.hash === "#comps") switchTab("comps");
}

async function init() {
  bindSliders();
  bindTabs();
  $("#btn-demo")?.addEventListener("click", runQuickDemo);
  $("#btn-analyze")?.addEventListener("click", runFullAnalysis);
  $("#btn-lookup")?.addEventListener("click", lookupMarketFromForm);
  $("#btn-lookup-form")?.addEventListener("click", lookupMarketFromForm);
  $("#prop-street")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      lookupMarketFromForm();
    }
  });
  // Mobile: show tab switcher via brand long-press isn't needed —
  // add compact tabs under nav when CSS hides desktop tabs
  if (!$(".tabs-mobile")) {
    const mobile = document.createElement("div");
    mobile.className = "tabs tabs-mobile";
    mobile.style.cssText = "display:none;padding:0 20px 10px;gap:6px";
    mobile.innerHTML = `
      <button type="button" class="tab" data-tab="refinance">Refinance</button>
      <button type="button" class="tab" data-tab="comps">Comps</button>
    `;
    $(".topnav")?.appendChild(mobile);
    const mq = window.matchMedia("(max-width: 640px)");
    const sync = () => {
      mobile.style.display = mq.matches ? "flex" : "none";
    };
    sync();
    mq.addEventListener("change", sync);
    mobile.querySelectorAll(".tab").forEach((t) => {
      t.addEventListener("click", () => switchTab(t.dataset.tab));
    });
  }
  await loadCatalog();
}

init();

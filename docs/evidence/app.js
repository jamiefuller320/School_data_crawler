/**
 * Evidence prototype — paragraph summaries + expandable sources.
 * No score bars; coverage is qualitative.
 */

const CORE_AREAS = {
  curriculum: "Curriculum",
  enrichment: "Enrichment & clubs",
  ethos: "Ethos & values",
  behaviour: "Behaviour & pastoral care",
  send: "SEND & inclusion",
  community: "Community & parents",
};

const SOURCE_LABELS = {
  "school-website": "School website",
  "school-document": "School document",
  "local-news": "Local news",
  "social-media": "Social media",
  other: "Other",
};

const state = {
  capture: null,
  learned: null,
  query: "",
  sort: "name",
  selectedUrn: null,
  expandedAreas: new Set(),
  expandedSources: new Set(),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function coverageLevel(area) {
  const signals = area.signals || [];
  const offerings = area.offerings || [];
  const confidence = area.confidence ?? 0;
  if (!signals.length && !offerings.length) {
    return { id: "none", label: "Not found in scan", className: "cov-none" };
  }
  if (signals.length >= 3 && confidence >= 0.55) {
    return { id: "rich", label: "Well documented", className: "cov-rich" };
  }
  if (signals.length >= 1 || offerings.length) {
    return { id: "some", label: "Some detail", className: "cov-some" };
  }
  return { id: "thin", label: "Thin", className: "cov-thin" };
}

function parentParagraph(area) {
  const offerings = area.offerings || [];
  const signals = area.signals || [];
  const label = CORE_AREAS[area.area] || area.area;
  const cov = coverageLevel(area);

  if (cov.id === "none") {
    return `We did not find much about ${label.toLowerCase()} on the pages and documents scanned for this school. Worth asking on a visit or checking the school's website directly.`;
  }

  if (offerings.length >= 2) {
    const shown = offerings.slice(0, 6).join(", ");
    const extra = offerings.length > 6 ? ` and ${offerings.length - 6} more` : "";
    const corroboration =
      signals.length >= 2
        ? ` Information appears across ${countDistinctUrls(signals)} page${countDistinctUrls(signals) === 1 ? "" : "s"}.`
        : "";
    return `The school website lists ${shown}${extra}.${corroboration}`;
  }

  if (signals.length === 1 && signals[0].text.length < 120) {
    return `The school mentions ${signals[0].text.toLowerCase().startsWith("the ") ? signals[0].text : signals[0].text}. See the source link below for the original page.`;
  }

  const best = signals.find((s) => s.text.length > 60) || signals[0];
  if (best) {
    return best.text;
  }

  return area.summary || `Some material related to ${label.toLowerCase()} was found on the school site.`;
}

function countDistinctUrls(signals) {
  return new Set(signals.map((s) => s.sourceUrl)).size;
}

function groupSources(area, record) {
  const groups = {
    "school-website": [],
    "school-document": [],
    "local-news": [],
    other: [],
  };

  for (const signal of area.signals || []) {
    const key =
      signal.sourceType === "school-website"
        ? "school-website"
        : signal.sourceType === "school-document"
          ? "school-document"
          : signal.sourceType === "local-news"
            ? "local-news"
            : "other";
    groups[key].push(signal);
  }

  const docs = (record.documentInventory || []).filter(
    (d) => d.status === "extracted" || d.status === "discovered",
  );
  for (const doc of docs) {
    const blob = `${doc.label} ${doc.url}`.toLowerCase();
    const areaKey = area.area;
    const relevant =
      (areaKey === "curriculum" &&
        /curriculum|subject|overview|prospectus/.test(blob)) ||
      (areaKey === "enrichment" && /club|sport|extra/.test(blob)) ||
      (areaKey === "send" && /send|sen|inclusion|senco/.test(blob)) ||
      (areaKey === "behaviour" && /safeguard|behav|pastoral/.test(blob)) ||
      (areaKey === "ethos" && /ethos|value|welcome/.test(blob)) ||
      (areaKey === "community" && /parent|community|pta/.test(blob));
    if (relevant) {
      groups["school-document"].push({
        text: doc.label || "Document",
        sourceUrl: doc.url,
        sourceType: "school-document",
        pageTitle: doc.label,
        meta: doc.status,
      });
    }
  }

  return groups;
}

function evidenceCount(area, record) {
  const groups = groupSources(area, record);
  return Object.values(groups).reduce((n, arr) => n + arr.length, 0);
}

function schoolCoverageSummary(record) {
  const areas = (record.areas || []).filter(
    (a) => coverageLevel(a).id !== "none",
  );
  return areas.length;
}

function renderLearnedTerms() {
  const el = document.getElementById("learned-terms");
  const terms = state.learned?.terms || {};
  const ranked = Object.entries(terms)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 24);
  if (!ranked.length) {
    el.innerHTML = `<p class="muted">No discovery lexicon yet — run a capture batch with learned terms enabled.</p>`;
    return;
  }
  el.innerHTML = `
    <p class="muted">Terms that scored well on scanned pages (used to find similar pages on other schools):</p>
    <div class="chip-row">
      ${ranked
        .map(
          ([term, weight]) =>
            `<span class="chip chip-learned" title="Seen ${weight} time(s) in useful evidence">${escapeHtml(term)}</span>`,
        )
        .join("")}
    </div>`;
}

function renderEmergingThemes() {
  const el = document.getElementById("emerging-themes");
  const themeCounts = new Map();
  const coreThemeWords = new Set(
    Object.keys(CORE_AREAS).flatMap((k) => k.split("_")),
  );

  for (const record of state.capture?.records || []) {
    for (const area of record.areas || []) {
      for (const theme of area.themes || []) {
        const t = theme.toLowerCase().trim();
        if (!t || t.length < 3) continue;
        themeCounts.set(t, (themeCounts.get(t) || 0) + 1);
      }
    }
  }

  const emerging = [...themeCounts.entries()]
    .filter(([t]) => !coreThemeWords.has(t))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 16);

  if (!emerging.length) {
    el.innerHTML = "";
    return;
  }

  el.innerHTML = `
    <h3>Emerging themes across this pilot</h3>
    <p class="muted">Recurring topics from scanned content — potential future focus areas beyond the core set.</p>
    <div class="chip-row">
      ${emerging
        .map(
          ([theme, count]) =>
            `<span class="chip chip-theme" title="${count} school-area hits">${escapeHtml(theme)}</span>`,
        )
        .join("")}
    </div>`;
}

function renderStats() {
  const records = state.capture?.records || [];
  const withEvidence = records.filter((r) => schoolCoverageSummary(r) > 0).length;
  const signals = records.reduce(
    (sum, r) =>
      sum + (r.areas || []).reduce((s, a) => s + (a.signals || []).length, 0),
    0,
  );
  const docs = records.reduce((sum, r) => sum + (r.documentsDiscovered || 0), 0);
  const learnedCount = Object.keys(state.learned?.terms || {}).length;

  document.getElementById("stat-schools").textContent = String(records.length);
  document.getElementById("stat-covered").textContent = String(withEvidence);
  document.getElementById("stat-signals").textContent = String(signals);
  document.getElementById("stat-docs").textContent = String(docs);
  document.getElementById("stat-learned").textContent = String(learnedCount);
  document.getElementById("generated-at").textContent =
    state.capture?.generatedAt || "—";
}

function filteredRecords() {
  const records = [...(state.capture?.records || [])];
  const q = state.query.trim().toLowerCase();
  const filtered = q
    ? records.filter(
        (r) =>
          r.name.toLowerCase().includes(q) || String(r.urn).includes(q),
      )
    : records;

  filtered.sort((a, b) => {
    if (state.sort === "coverage") {
      return schoolCoverageSummary(b) - schoolCoverageSummary(a);
    }
    return a.name.localeCompare(b.name);
  });
  return filtered;
}

function renderCards() {
  const grid = document.getElementById("school-grid");
  const records = filteredRecords();
  if (!records.length) {
    grid.innerHTML = `<p class="empty">No schools match your search.</p>`;
    return;
  }

  grid.innerHTML = records
    .map((record) => {
      const documented = schoolCoverageSummary(record);
      const badges = (record.areas || [])
        .filter((a) => coverageLevel(a).id !== "none")
        .slice(0, 4)
        .map((a) => {
          const cov = coverageLevel(a);
          return `<span class="cov-pill ${cov.className}">${escapeHtml(CORE_AREAS[a.area] || a.area)}</span>`;
        })
        .join("");

      return `
      <article class="card" tabindex="0" data-urn="${escapeHtml(record.urn)}" aria-label="View ${escapeHtml(record.name)}">
        <h2>${escapeHtml(record.name)}</h2>
        <div class="meta">URN ${escapeHtml(record.urn)} · ${documented} of ${Object.keys(CORE_AREAS).length} areas with something found</div>
        <div class="cov-row">${badges || '<span class="muted">Nothing found in scan</span>'}</div>
      </article>`;
    })
    .join("");

  grid.querySelectorAll(".card").forEach((card) => {
    const open = () => showDetail(card.dataset.urn);
    card.addEventListener("click", open);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
  });
}

function renderSourceGroup(areaKey, type, items) {
  if (!items.length) return "";
  const groupId = `${areaKey}-${type}`;
  const open = state.expandedSources.has(groupId);
  return `
    <details class="source-group" ${open ? "open" : ""} data-group="${escapeHtml(groupId)}">
      <summary>${escapeHtml(SOURCE_LABELS[type] || type)} (${items.length})</summary>
      <ul class="source-list">
        ${items
          .map((item) => {
            const title = item.pageTitle || item.text?.slice(0, 80) || "Source";
            const quote =
              item.text && item.text.length > 20 && item.text !== title
                ? `<blockquote>${escapeHtml(item.text)}</blockquote>`
                : "";
            return `
          <li>
            <a href="${escapeHtml(item.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a>
            ${quote}
          </li>`;
          })
          .join("")}
      </ul>
    </details>`;
}

function renderAreaBlock(area, record) {
  const areaKey = area.area;
  const cov = coverageLevel(area);
  const paragraph = parentParagraph(area);
  const offerings = area.offerings || [];
  const groups = groupSources(area, record);
  const sourceCount = evidenceCount(area, record);
  const expanded = state.expandedAreas.has(areaKey);

  const offeringsHtml = offerings.length
    ? `<div class="offerings"><span class="offerings-label">Listed on site:</span> ${offerings
        .map((o) => `<span class="chip">${escapeHtml(o)}</span>`)
        .join("")}</div>`
    : "";

  const sourcesHtml =
    sourceCount > 0
      ? `
    <div class="sources-panel ${expanded ? "is-open" : ""}">
      <button type="button" class="sources-toggle" data-area="${escapeHtml(areaKey)}" aria-expanded="${expanded}">
        ${expanded ? "Hide" : "Show"} sources (${sourceCount})
      </button>
      <div class="sources-body" ${expanded ? "" : "hidden"}>
        ${renderSourceGroup(areaKey, "school-website", groups["school-website"])}
        ${renderSourceGroup(areaKey, "school-document", groups["school-document"])}
        ${renderSourceGroup(areaKey, "local-news", groups["local-news"])}
        ${renderSourceGroup(areaKey, "other", groups.other)}
      </div>
    </div>`
      : "";

  return `
    <section class="area-evidence">
      <div class="area-head">
        <h3>${escapeHtml(CORE_AREAS[area.area] || area.area)}</h3>
        <span class="cov-badge ${cov.className}">${escapeHtml(cov.label)}</span>
      </div>
      <p class="area-summary">${escapeHtml(paragraph)}</p>
      ${offeringsHtml}
      ${sourcesHtml}
    </section>`;
}

function renderDetail(record) {
  const panel = document.getElementById("detail-panel");
  if (!record) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }

  const areasHtml = (record.areas || [])
    .filter((a) => CORE_AREAS[a.area])
    .map((a) => renderAreaBlock(a, record))
    .join("");

  const otherAreas = (record.areas || []).filter((a) => !CORE_AREAS[a.area]);
  const otherHtml = otherAreas.length
    ? `<section class="area-evidence area-other">
        <h3>Other scanned topics</h3>
        ${otherAreas.map((a) => renderAreaBlock(a, record)).join("")}
      </section>`
    : "";

  panel.classList.remove("hidden");
  panel.innerHTML = `
    <div class="detail-header">
      <div>
        <h2>${escapeHtml(record.name)}</h2>
        <div class="meta">URN ${escapeHtml(record.urn)} · scanned ${escapeHtml(record.assessedAt)} · ${record.sourcesScanned} pages/sources</div>
      </div>
      <button class="close-btn" type="button" id="close-detail">Close</button>
    </div>
    <p class="detail-lede">Summaries below are assembled from what this school publishes online. They are not judgments of quality — expand sources to read originals.</p>
    ${areasHtml}
    ${otherHtml}
  `;

  document.getElementById("close-detail").addEventListener("click", () => {
    state.selectedUrn = null;
    state.expandedAreas.clear();
    renderDetail(null);
  });

  panel.querySelectorAll(".sources-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.area;
      if (state.expandedAreas.has(key)) state.expandedAreas.delete(key);
      else state.expandedAreas.add(key);
      renderDetail(record);
    });
  });

  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showDetail(urn) {
  state.selectedUrn = urn;
  const record = (state.capture?.records || []).find((r) => r.urn === urn);
  renderDetail(record || null);
}

function bindControls() {
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    renderCards();
  });
  document.getElementById("sort").addEventListener("change", (e) => {
    state.sort = e.target.value;
    renderCards();
  });
}

async function loadData() {
  const [captureRes, learnedRes] = await Promise.all([
    fetch("./data/qualitative-capture.json"),
    fetch("./data/learned-url-terms.json"),
  ]);
  if (!captureRes.ok) {
    throw new Error(`Failed to load capture data (${captureRes.status})`);
  }
  state.capture = await captureRes.json();
  if (learnedRes.ok) {
    state.learned = await learnedRes.json();
  } else {
    state.learned = { terms: {} };
  }
}

async function init() {
  try {
    await loadData();
    renderLearnedTerms();
    renderEmergingThemes();
    renderStats();
    bindControls();
    renderCards();
  } catch (error) {
    document.getElementById("school-grid").innerHTML = `
      <p class="empty">Could not load prototype data. ${escapeHtml(error.message)}</p>`;
  }
}

init();

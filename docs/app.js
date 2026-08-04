const AREA_LABELS = {
  curriculum: "Curriculum",
  enrichment: "Enrichment",
  ethos: "Ethos",
  behaviour: "Behaviour",
  send: "SEND",
  community: "Community",
};

const state = {
  data: null,
  query: "",
  sort: "name",
  selectedUrn: null,
};

function scoreClass(score) {
  if (score >= 60) return "score-high";
  if (score >= 35) return "score-mid";
  return "score-low";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatSourceType(type) {
  return String(type || "other").replaceAll("-", " ");
}

function averageAreaScores(records) {
  const totals = {};
  const counts = {};
  for (const record of records) {
    for (const area of record.areas || []) {
      totals[area.area] = (totals[area.area] || 0) + area.score;
      counts[area.area] = (counts[area.area] || 0) + 1;
    }
  }
  return Object.keys(AREA_LABELS)
    .map((area) => ({
      area,
      avg: counts[area] ? Math.round(totals[area] / counts[area]) : 0,
    }))
    .sort((a, b) => b.avg - a.avg);
}

function renderStats() {
  const records = state.data.records || [];
  const withSignals = records.filter((r) =>
    (r.areas || []).some((a) => (a.signals || []).length > 0),
  ).length;
  const avgScore =
    records.length === 0
      ? 0
      : Math.round(
          records.reduce((sum, r) => {
            const areas = r.areas || [];
            const schoolAvg =
              areas.reduce((s, a) => s + a.score, 0) / (areas.length || 1);
            return sum + schoolAvg;
          }, 0) / records.length,
        );

  document.getElementById("stat-schools").textContent = String(records.length);
  document.getElementById("stat-signals").textContent = String(
    records.reduce(
      (sum, r) =>
        sum +
        (r.areas || []).reduce((s, a) => s + (a.signals || []).length, 0),
      0,
    ),
  );
  document.getElementById("stat-covered").textContent = String(withSignals);
  document.getElementById("stat-avg").textContent = String(avgScore);
  document.getElementById("generated-at").textContent =
    state.data.generatedAt || "—";
  document.getElementById("pilot-la").textContent =
    state.data.stats?.la || "Hampshire";
}

function filteredRecords() {
  const records = [...(state.data.records || [])];
  const q = state.query.trim().toLowerCase();
  const filtered = q
    ? records.filter(
        (r) =>
          r.name.toLowerCase().includes(q) || String(r.urn).includes(q),
      )
    : records;

  filtered.sort((a, b) => {
    if (state.sort === "score") {
      const avg = (r) =>
        (r.areas || []).reduce((s, x) => s + x.score, 0) /
        ((r.areas || []).length || 1);
      return avg(b) - avg(a);
    }
    if (state.sort === "signals") {
      const count = (r) =>
        (r.areas || []).reduce((s, x) => s + (x.signals || []).length, 0);
      return count(b) - count(a);
    }
    return a.name.localeCompare(b.name);
  });
  return filtered;
}

function renderAreaBars(areas) {
  return (areas || [])
    .map((area) => {
      const label = AREA_LABELS[area.area] || area.area;
      return `
        <div class="area-row">
          <span>${escapeHtml(label)}</span>
          <div class="bar-track">
            <div class="bar-fill ${scoreClass(area.score)}" style="width:${area.score}%"></div>
          </div>
          <span>${area.score}</span>
        </div>`;
    })
    .join("");
}

function renderCards() {
  const grid = document.getElementById("school-grid");
  const records = filteredRecords();
  if (!records.length) {
    grid.innerHTML = `<p class="empty">No schools match your search.</p>`;
    return;
  }

  grid.innerHTML = records
    .map(
      (record) => `
      <article class="card" tabindex="0" data-urn="${escapeHtml(record.urn)}" aria-label="View ${escapeHtml(record.name)}">
        <h2>${escapeHtml(record.name)}</h2>
        <div class="meta">URN ${escapeHtml(record.urn)} · ${record.sourcesScanned} source page(s) · engine ${escapeHtml(record.engineVersion || "")}</div>
        <div class="area-bars">${renderAreaBars(record.areas)}</div>
      </article>`,
    )
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

function renderDetail(record) {
  const panel = document.getElementById("detail-panel");
  if (!record) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }

  const areasHtml = (record.areas || [])
    .map((area) => {
      const signals = (area.signals || [])
        .map(
          (signal) => `
          <blockquote class="signal">
            <p>${escapeHtml(signal.text)}</p>
            <div class="source">
              <a href="${escapeHtml(signal.sourceUrl)}" target="_blank" rel="noopener noreferrer">
                ${escapeHtml(formatSourceType(signal.sourceType))}
              </a>
              ${signal.section ? ` · ${escapeHtml(signal.section)}` : ""}
            </div>
          </blockquote>`,
        )
        .join("");

      const themes = (area.themes || [])
        .map((t) => `<span class="theme">${escapeHtml(t)}</span>`)
        .join("");

      return `
        <section class="area-block">
      <h3>${escapeHtml(AREA_LABELS[area.area] || area.area)} · score ${area.score} · confidence ${Math.round(area.confidence * 100)}%</h3>
      <p class="summary">${escapeHtml(area.summary)}</p>
      ${area.confidence < 0.35 ? `<p class="summary"><em>Low confidence — treat as indicative only; visit source links to verify.</em></p>` : ""}
          ${themes ? `<div class="themes">${themes}</div>` : ""}
      ${
        (area.offerings || []).length
          ? `<div class="offerings"><strong>Listed provision:</strong> ${(area.offerings || [])
              .map((o) => `<span class="theme">${escapeHtml(o)}</span>`)
              .join("")}</div>`
          : ""
      }
          ${signals || "<p class='summary'>No footnoted excerpts for this area.</p>"}
        </section>`;
    })
    .join("");

  panel.classList.remove("hidden");
  panel.innerHTML = `
    <div class="detail-header">
      <div>
        <h2>${escapeHtml(record.name)}</h2>
        <div class="meta">URN ${escapeHtml(record.urn)} · assessed ${escapeHtml(record.assessedAt)} · engine ${escapeHtml(record.engineVersion)}</div>
      </div>
      <button class="close-btn" type="button" id="close-detail">Close</button>
    </div>
    ${areasHtml}
  `;

  document.getElementById("close-detail").addEventListener("click", () => {
    state.selectedUrn = null;
    renderDetail(null);
  });
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showDetail(urn) {
  state.selectedUrn = urn;
  const record = (state.data.records || []).find((r) => r.urn === urn);
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
  const response = await fetch("./data/qualitative-capture.json");
  if (!response.ok) {
    throw new Error(`Failed to load pilot data (${response.status})`);
  }
  state.data = await response.json();
}

async function init() {
  try {
    await loadData();
    renderStats();
    bindControls();
    renderCards();
    if (state.data.records?.length === 1) {
      showDetail(state.data.records[0].urn);
    }
  } catch (error) {
    document.getElementById("school-grid").innerHTML = `
      <p class="empty">Could not load pilot data. ${escapeHtml(error.message)}</p>`;
  }
}

init();

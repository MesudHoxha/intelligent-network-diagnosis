"use strict";

const API = Object.freeze({
  health: "/api/v1/health",
  overview: "/api/v1/overview",
  comparison: "/api/v1/comparison",
  cases: "/api/v1/cases",
  provenance: "/api/v1/provenance",
});

const METHOD_LABELS = Object.freeze({
  rule_based_p6_v1: "Rule-based",
  machine_learning_p6_v1: "Machine Learning",
  hybrid_p6_v1: "Hybrid",
});

const FAULT_LABELS = Object.freeze({
  no_fault: "No fault",
  missing_static_route: "Missing static route",
  wrong_next_hop: "Wrong next hop",
  wrong_default_gateway: "Wrong default gateway",
  interface_down: "Interface down",
  acl_block: "ACL block",
});

const MASK_LABELS = Object.freeze({
  clean: "Clean",
  mask_source_gateway_family: "Source gateway family",
  mask_route_family: "Route family",
  mask_interface_state: "Interface state",
  mask_policy_state: "Policy state",
});

const METRICS = Object.freeze([
  ["accuracy", "Accuracy"],
  ["macro_f1", "Macro F1"],
  ["exact_diagnosis_rate", "Exact diagnosis"],
  ["affected_prefix_rate", "Affected prefix"],
  ["coverage", "Coverage"],
  ["abstention_rate", "Abstention"],
  ["insufficient_evidence_rate", "Insufficient evidence"],
]);

const PRIMARY_METRICS = Object.freeze([
  ["accuracy", "Accuracy"],
  ["macro_f1", "Macro F1"],
  ["coverage", "Coverage"],
  ["insufficient_evidence_rate", "Insufficient evidence"],
]);

const caseState = {
  page: 1,
  pageSize: 25,
  totalPages: 0,
  filters: {},
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function labelFor(map, value) {
  return map[value] || String(value || "Not available");
}

function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function meterValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(100, Math.max(0, numeric * 100));
}

function displayError(error) {
  if (error && error.payload && error.payload.error) {
    const body = error.payload.error;
    return `${body.code}: ${body.message}`;
  }
  return "The local read-only API could not be reached.";
}

async function requestJson(path) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }
  if (!response.ok || !payload || !payload.data) {
    const error = new Error(`Request failed with status ${response.status}`);
    error.payload = payload;
    throw error;
  }
  return payload.data;
}

function setLoading(stateId, message) {
  const state = document.getElementById(stateId);
  state.hidden = false;
  state.className = "state-box";
  state.innerHTML = `<span class="spinner" aria-hidden="true"></span>${escapeHtml(message)}`;
}

function setError(stateId, message, retryTarget) {
  const state = document.getElementById(stateId);
  state.hidden = false;
  state.className = "state-box is-error";
  state.innerHTML = `<p>${escapeHtml(message)}</p><button type="button" class="button button-secondary" data-retry="${escapeHtml(retryTarget)}">Retry</button>`;
}

function showContent(stateId, contentId) {
  document.getElementById(stateId).hidden = true;
  document.getElementById(contentId).hidden = false;
}

function renderOverview(data) {
  const comparisonType = data.comparison_type === "DESCRIPTIVE_ONLY"
    ? "Descriptive only"
    : data.comparison_type.replaceAll("_", " ");
  const stats = [
    [data.total_input_count, "Total report-only inputs", "24 clean + 96 deterministic masks"],
    [data.clean_input_count, "Clean inputs", "Independent controlled test cases"],
    [data.masked_input_count, "Masked inputs", "Derived evidence-availability views"],
    [comparisonType, "Comparison type", "No superiority test performed"],
  ];
  document.getElementById("overview-stats").innerHTML = stats.map(([value, label, note]) => `
    <article class="stat-card">
      <span class="stat-label">${escapeHtml(label)}</span>
      <strong class="stat-value">${escapeHtml(value)}</strong>
      <span class="stat-note">${escapeHtml(note)}</span>
    </article>`).join("");

  document.getElementById("class-count").textContent = String(data.class_order.length);
  document.getElementById("class-list").innerHTML = data.class_order
    .map((item) => `<span class="chip">${escapeHtml(labelFor(FAULT_LABELS, item))}</span>`)
    .join("");

  document.getElementById("method-count").textContent = String(data.method_order.length);
  document.getElementById("method-list").innerHTML = data.method_order
    .map((item, index) => `<div class="method-row"><span class="method-index">0${index + 1}</span><span>${escapeHtml(labelFor(METHOD_LABELS, item))}</span></div>`)
    .join("");

  const faultSelect = document.getElementById("fault-filter");
  data.class_order.forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = labelFor(FAULT_LABELS, item);
    faultSelect.append(option);
  });
  const methodSelect = document.getElementById("method-filter");
  data.method_order.forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = labelFor(METHOD_LABELS, item);
    methodSelect.append(option);
  });

  document.getElementById("overview-boundary-text").textContent = data.limitations[0];
  showContent("overview-state", "overview-content");
}

async function loadOverview() {
  setLoading("overview-state", "Loading accepted overview…");
  try {
    renderOverview(await requestJson(API.overview));
  } catch (error) {
    setError("overview-state", displayError(error), "overview");
  }
}

function renderComparison(data) {
  document.getElementById("comparison-cards").innerHTML = data.methods.map((method) => {
    const lines = PRIMARY_METRICS.map(([key, label]) => {
      const exact = method.metrics[key];
      return `<div class="metric-line">
        <div class="metric-line-header"><span>${escapeHtml(label)}</span><strong title="Exact API value: ${escapeHtml(exact)}">${escapeHtml(percent(exact))}</strong></div>
        <div class="meter" aria-hidden="true"><span style="--value: ${meterValue(exact)}%"></span></div>
      </div>`;
    }).join("");
    return `<article class="method-card">
      <div><h3>${escapeHtml(labelFor(METHOD_LABELS, method.method_id))}</h3><span class="sample-count">${escapeHtml(method.metrics.sample_count)} accepted inputs</span></div>
      <div class="metric-stack">${lines}</div>
    </article>`;
  }).join("");

  document.getElementById("comparison-table-head").innerHTML = `<tr><th scope="col">Metric</th>${data.methods
    .map((method) => `<th scope="col">${escapeHtml(labelFor(METHOD_LABELS, method.method_id))}</th>`)
    .join("")}</tr>`;
  document.getElementById("comparison-table-body").innerHTML = METRICS.map(([key, label]) => `<tr>
    <td>${escapeHtml(label)}</td>
    ${data.methods.map((method) => `<td title="Exact API value: ${escapeHtml(method.metrics[key])}">${escapeHtml(percent(method.metrics[key]))}</td>`).join("")}
  </tr>`).join("");

  document.querySelectorAll("[data-scope]").forEach((button) => {
    const selected = button.dataset.scope === data.scope;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  showContent("comparison-state", "comparison-content");
}

async function loadComparison(scope = "overall") {
  document.getElementById("comparison-content").hidden = true;
  setLoading("comparison-state", "Loading accepted metrics…");
  try {
    const query = new URLSearchParams({ scope });
    renderComparison(await requestJson(`${API.comparison}?${query}`));
  } catch (error) {
    setError("comparison-state", displayError(error), "comparison");
  }
}

function predictionMarkup(prediction) {
  const resolved = prediction.status === "RESOLVED";
  return `<span class="prediction-label">${escapeHtml(labelFor(FAULT_LABELS, prediction.predicted_fault_type))}</span>
    <span class="status-label${resolved ? "" : " is-unresolved"}">${escapeHtml(prediction.status.replaceAll("_", " "))}</span>`;
}

function renderCases(data) {
  const { items, pagination } = data;
  caseState.page = pagination.page;
  caseState.totalPages = pagination.total_pages;

  const state = document.getElementById("cases-state");
  const content = document.getElementById("cases-content");
  if (items.length === 0) {
    content.hidden = true;
    state.hidden = false;
    state.className = "state-box is-empty";
    state.innerHTML = "No accepted cases match the selected filters.";
    return;
  }

  document.getElementById("case-table-body").innerHTML = items.map((item) => {
    const predictions = Object.fromEntries(item.predictions.map((prediction) => [prediction.method_id, prediction]));
    return `<tr>
      <td data-label="Input">${escapeHtml(item.input_id)}</td>
      <td data-label="Context">${escapeHtml(item.context_id)}</td>
      <td data-label="Mask"><span class="mask-label">${escapeHtml(labelFor(MASK_LABELS, item.mask_id))}</span></td>
      <td data-label="Expected">${escapeHtml(labelFor(FAULT_LABELS, item.expected_fault_type))}</td>
      <td data-label="Rule" class="prediction-cell">${predictionMarkup(predictions.rule_based_p6_v1)}</td>
      <td data-label="ML" class="prediction-cell">${predictionMarkup(predictions.machine_learning_p6_v1)}</td>
      <td data-label="Hybrid" class="prediction-cell">${predictionMarkup(predictions.hybrid_p6_v1)}</td>
      <td data-label="Inspect"><button class="row-action" type="button" data-case-id="${escapeHtml(item.input_id)}" aria-label="Inspect ${escapeHtml(item.input_id)}">→</button></td>
    </tr>`;
  }).join("");

  document.getElementById("case-result-count").textContent = `${pagination.total_items} accepted ${pagination.total_items === 1 ? "case" : "cases"}`;
  document.getElementById("case-sort").textContent = "Sorted by input ID · ascending";
  document.getElementById("page-status").textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
  document.getElementById("previous-page").disabled = pagination.page <= 1;
  document.getElementById("next-page").disabled = pagination.page >= pagination.total_pages;
  showContent("cases-state", "cases-content");
}

function currentFilters() {
  const values = Object.fromEntries(new FormData(document.getElementById("case-filters")).entries());
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ""));
}

async function loadCases(page = 1) {
  document.getElementById("cases-content").hidden = true;
  setLoading("cases-state", "Loading verified cases…");
  caseState.page = page;
  const query = new URLSearchParams({ ...caseState.filters, page: String(page), page_size: String(caseState.pageSize) });
  try {
    renderCases(await requestJson(`${API.cases}?${query}`));
  } catch (error) {
    setError("cases-state", displayError(error), "cases");
  }
}

function diagnosticValue(diagnosis, key) {
  if (!diagnosis || diagnosis[key] === null || diagnosis[key] === undefined) return "Not defined";
  return diagnosis[key];
}

function renderCaseDetail(data) {
  document.getElementById("case-dialog-title").textContent = data.input_id;
  const commonFields = [
    ["Expected fault", labelFor(FAULT_LABELS, data.expected_fault_type)],
    ["Evidence mask", labelFor(MASK_LABELS, data.mask_id)],
    ["Context", data.context_id],
    ["Topology", data.topology_id],
    ["Direction", data.direction],
    ["Source", data.source_node],
    ["Route observer", data.route_observer_node],
    ["Destination", data.destination_prefix],
  ];
  const predictions = data.predictions.map((prediction) => `<article class="prediction-detail">
    <h3>${escapeHtml(labelFor(METHOD_LABELS, prediction.method_id))}</h3>
    <dl>
      <dt>Status</dt><dd>${escapeHtml(prediction.status.replaceAll("_", " "))}</dd>
      <dt>Fault</dt><dd>${escapeHtml(labelFor(FAULT_LABELS, prediction.predicted_fault_type))}</dd>
      <dt>Confidence</dt><dd title="Exact API value: ${escapeHtml(prediction.confidence)}">${escapeHtml(prediction.confidence === null ? "Not defined" : percent(prediction.confidence))}</dd>
      <dt>Location</dt><dd>${escapeHtml(diagnosticValue(prediction.diagnosis, "fault_location"))}</dd>
      <dt>Prefix</dt><dd>${escapeHtml(diagnosticValue(prediction.diagnosis, "affected_prefix"))}</dd>
    </dl>
    <p class="prediction-reason">${escapeHtml(prediction.reason)}</p>
  </article>`).join("");
  const evidence = Object.keys(data.evidence.features).sort().map((feature) => {
    const value = data.evidence.features[feature];
    return `<tr>
      <td>${escapeHtml(feature)}</td>
      <td><span class="evidence-value is-${escapeHtml(value)}">${escapeHtml(value)}</span></td>
      <td>${escapeHtml(data.evidence.availability[feature])}</td>
    </tr>`;
  }).join("");

  document.getElementById("case-detail-state").hidden = true;
  document.getElementById("case-detail-content").innerHTML = `
    <div class="detail-grid">${commonFields.map(([label, value]) => `<div class="detail-field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>
    <div class="prediction-detail-grid">${predictions}</div>
    <article class="evidence-panel">
      <h3>Normalized evidence availability</h3>
      <div class="table-wrap">
        <table class="data-table evidence-table">
          <thead><tr><th scope="col">Feature</th><th scope="col">Value</th><th scope="col">Availability</th></tr></thead>
          <tbody>${evidence}</tbody>
        </table>
      </div>
    </article>`;
}

async function openCase(inputId) {
  const dialog = document.getElementById("case-dialog");
  document.getElementById("case-detail-content").innerHTML = "";
  setLoading("case-detail-state", "Loading verified case detail…");
  if (!dialog.open) dialog.showModal();
  try {
    renderCaseDetail(await requestJson(`${API.cases}/${encodeURIComponent(inputId)}`));
  } catch (error) {
    setError("case-detail-state", displayError(error), "case-detail");
  }
}

function renderProvenance(data) {
  const cards = [
    [data.projection_source_count, "Verified projection sources", "JSON and JSONL allowlist"],
    [data.selected_ml_candidate, "Selected ML candidate", "Frozen before report-only evaluation"],
    [data.selected_hybrid_policy, "Selected Hybrid policy", "Rule first, ML fallback"],
  ];
  document.getElementById("provenance-summary").innerHTML = cards.map(([value, label, note]) => `
    <article class="stat-card"><span class="stat-label">${escapeHtml(label)}</span><strong class="stat-value">${escapeHtml(value)}</strong><span class="stat-note">${escapeHtml(note)}</span></article>`).join("");

  document.getElementById("root-list").innerHTML = data.roots.map((root) => `
    <div class="root-row">
      <strong>${escapeHtml(root.artifact_id.replaceAll("_", " "))}</strong>
      <span class="root-path">${escapeHtml(root.path)}</span>
      <span class="root-hash" title="SHA-256">${escapeHtml(root.sha256)}</span>
    </div>`).join("");
  document.getElementById("limitations-list").innerHTML = data.limitations
    .map((limitation) => `<li>${escapeHtml(limitation)}</li>`)
    .join("");
  showContent("provenance-state", "provenance-content");
}

async function loadProvenance() {
  setLoading("provenance-state", "Verifying provenance projection…");
  try {
    renderProvenance(await requestJson(API.provenance));
  } catch (error) {
    setError("provenance-state", displayError(error), "provenance");
  }
}

async function loadHealth() {
  const status = document.getElementById("service-status");
  const text = document.getElementById("service-status-text");
  try {
    const data = await requestJson(API.health);
    status.className = "service-status is-ready";
    text.textContent = `${data.status} · ${data.projection_source_count}/15 sources`;
  } catch (error) {
    status.className = "service-status is-error";
    text.textContent = "Artifact boundary unavailable";
  }
}

function setupInteractions() {
  document.getElementById("scope-control").addEventListener("click", (event) => {
    const button = event.target.closest("[data-scope]");
    if (button) loadComparison(button.dataset.scope);
  });

  document.getElementById("case-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    caseState.filters = currentFilters();
    loadCases(1);
  });

  document.getElementById("method-filter").addEventListener("change", (event) => {
    const statusFilter = document.getElementById("status-filter");
    statusFilter.disabled = !event.target.value;
    if (!event.target.value) statusFilter.value = "";
  });

  document.getElementById("reset-filters").addEventListener("click", () => {
    document.getElementById("case-filters").reset();
    document.getElementById("status-filter").disabled = true;
    caseState.filters = {};
    loadCases(1);
  });

  document.getElementById("previous-page").addEventListener("click", () => loadCases(Math.max(1, caseState.page - 1)));
  document.getElementById("next-page").addEventListener("click", () => loadCases(Math.min(caseState.totalPages, caseState.page + 1)));

  document.getElementById("case-table-body").addEventListener("click", (event) => {
    const button = event.target.closest("[data-case-id]");
    if (button) openCase(button.dataset.caseId);
  });

  const dialog = document.getElementById("case-dialog");
  document.getElementById("close-case-dialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  document.addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry]");
    if (!retry) return;
    const target = retry.dataset.retry;
    if (target === "overview") loadOverview();
    if (target === "comparison") loadComparison(document.querySelector("[data-scope].is-selected")?.dataset.scope || "overall");
    if (target === "cases") loadCases(caseState.page);
    if (target === "provenance") loadProvenance();
  });

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        document.querySelectorAll(".nav-link").forEach((link) => {
          link.classList.toggle("is-active", link.dataset.section === entry.target.id);
        });
      });
    }, { rootMargin: "-28% 0px -62%", threshold: 0 });
    document.querySelectorAll(".dashboard-section").forEach((section) => observer.observe(section));
  }
}

async function initializeDashboard() {
  setupInteractions();
  await Promise.allSettled([
    loadHealth(),
    loadOverview(),
    loadComparison(),
    loadCases(),
    loadProvenance(),
  ]);
}

initializeDashboard();

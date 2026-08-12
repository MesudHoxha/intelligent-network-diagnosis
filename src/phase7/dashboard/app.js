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

const METHOD_DESCRIPTIONS = Object.freeze({
  rule_based_p6_v1: "Checks the evidence against fixed expert-defined diagnostic patterns.",
  machine_learning_p6_v1: "Uses the frozen trained model to select one of the six supported conditions.",
  hybrid_p6_v1: "Uses a rule diagnosis when available and the frozen ML fallback when evidence is missing.",
});

const FAULT_LABELS = Object.freeze({
  no_fault: "No network fault",
  missing_static_route: "Missing static route",
  wrong_next_hop: "Wrong next hop",
  wrong_default_gateway: "Wrong default gateway",
  interface_down: "Interface down",
  acl_block: "ACL block",
});

const MASK_LABELS = Object.freeze({
  clean: "Original evidence",
  mask_source_gateway_family: "Source gateway evidence missing",
  mask_route_family: "Routing evidence missing",
  mask_interface_state: "Interface-state evidence missing",
  mask_policy_state: "Security-policy evidence missing",
});

const STATUS_LABELS = Object.freeze({
  RESOLVED: "Diagnosis available",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  ABSTAINED: "No diagnosis by policy",
  NO_RULE_MATCH: "No matching rule",
});

const AVAILABILITY_LABELS = Object.freeze({
  observed: "Available",
  structurally_unavailable: "Not applicable",
  collection_unavailable: "Collection unavailable",
  masked_missing: "Intentionally hidden",
});

const FEATURE_DEFINITIONS = Object.freeze({
  source_expected_gateway_reachable: Object.freeze({
    label: "Expected gateway reachable",
    description: "Checks whether the source can reach its expected local gateway.",
  }),
  source_default_gateway_matches_expected: Object.freeze({
    label: "Default gateway configured correctly",
    description: "Checks whether the source uses the expected default gateway.",
  }),
  destination_reachable: Object.freeze({
    label: "Destination reachable",
    description: "Tests whether traffic from the source can reach the destination network.",
  }),
  route_to_destination_exists_on_observer: Object.freeze({
    label: "Route to destination exists",
    description: "Checks whether the routing device has a route to the destination network.",
  }),
  route_next_hop_matches_expected: Object.freeze({
    label: "Route uses the expected next hop",
    description: "Compares the configured route next hop with the expected next hop.",
  }),
  route_next_hop_reachable_from_observer: Object.freeze({
    label: "Configured next hop reachable",
    description: "Checks whether the routing device can reach the next hop currently in its route.",
  }),
  expected_next_hop_reachable_from_observer: Object.freeze({
    label: "Expected next hop reachable",
    description: "Checks whether the routing device can reach the expected transit next hop.",
  }),
  observer_egress_interface_oper_up: Object.freeze({
    label: "Outgoing interface active",
    description: "Checks whether the selected forwarding interface is operationally up.",
  }),
  destination_reachable_from_transit: Object.freeze({
    label: "Destination reachable from transit",
    description: "Tests whether the transit device can reach the destination downstream.",
  }),
  flow_blocked_by_policy: Object.freeze({
    label: "Traffic blocked by security policy",
    description: "Checks whether the inspected forwarding policy blocks the evaluated traffic flow.",
  }),
});

const METRICS = Object.freeze([
  Object.freeze({ key: "accuracy", label: "Accuracy", description: "Percentage of evaluated cases diagnosed with the correct fault type." }),
  Object.freeze({ key: "macro_f1", label: "Macro F1", description: "Balances precision and recall while giving equal importance to every supported condition." }),
  Object.freeze({ key: "exact_diagnosis_rate", label: "Exact diagnosis", description: "Cases where the complete diagnosis matched the known evaluation answer." }),
  Object.freeze({ key: "affected_prefix_rate", label: "Affected network", description: "Fault cases where the affected network prefix was identified correctly." }),
  Object.freeze({ key: "coverage", label: "Coverage", description: "Percentage of cases where the method provided a diagnosis." }),
  Object.freeze({ key: "abstention_rate", label: "No diagnosis by policy", description: "Cases where a method deliberately withheld a diagnosis under its fixed policy." }),
  Object.freeze({ key: "insufficient_evidence_rate", label: "Insufficient evidence", description: "Cases where the method did not diagnose because the available information was not enough." }),
]);

const PRIMARY_METRIC_KEYS = Object.freeze([
  "accuracy",
  "macro_f1",
  "coverage",
  "insufficient_evidence_rate",
]);

const SCENARIO_LABELS = Object.freeze({
  CTX_P6_E02_TOP02_CHAIN_OBSERVER_EDGE: "Topology 2 — Host A → Host B",
  CTX_P6_E06_TOP04_FILTER_BOUNDARY: "Topology 4 — Host A → Host B",
});

const FRIENDLY_LIMITATIONS = Object.freeze([
  "The 96 missing-evidence cases were created from 24 original test cases. They are not 96 independent network experiments.",
  "The comparison describes the accepted results; it does not statistically prove that one method is superior.",
  "Machine Learning and Hybrid have the same aggregate results in every accepted comparison scope.",
  "Results from this controlled laboratory do not by themselves prove performance on production networks.",
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

function nodeLabel(value) {
  const raw = String(value || "Not available");
  const host = raw.match(/^host([a-z])$/i);
  if (host) return `Host ${host[1].toUpperCase()}`;
  const device = raw.match(/^(r|fw)(\d+)$/i);
  if (device) return `${device[1].toUpperCase()}${device[2]}`;
  return raw.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function trafficPath(direction) {
  const match = String(direction || "").match(/^(.+)_to_(.+)$/);
  return match ? `${nodeLabel(match[1])} → ${nodeLabel(match[2])}` : labelFor({}, direction);
}

function topologyLabel(topologyId) {
  return String(topologyId || "Unknown topology")
    .replace(/^TOP_0*(\d+)/, "Topology $1")
    .replaceAll("_", " ")
    .replace(/\b(chain|branch|dual transit|asymmetric return|filter boundary)\b/gi, (value) => value.toLowerCase());
}

function scenarioLabel(value) {
  return SCENARIO_LABELS[value.context_id] || topologyLabel(value.topology_id);
}

function evidenceLabel(maskId) {
  return labelFor(MASK_LABELS, maskId || "clean");
}

function statusLabel(status) {
  return labelFor(STATUS_LABELS, status);
}

function metricDefinition(key) {
  return METRICS.find((metric) => metric.key === key);
}

function metricLabelMarkup(metric) {
  return `<span class="metric-name" title="${escapeHtml(metric.description)}">${escapeHtml(metric.label)} <span class="info-dot" aria-hidden="true">i</span></span>`;
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

function populateSelect(selectId, items, labels) {
  const select = document.getElementById(selectId);
  while (select.options.length > 1) select.remove(1);
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = labelFor(labels, item);
    select.append(option);
  });
}

function renderOverview(data) {
  const stats = [
    [data.total_input_count, "Total evaluated cases", "All accepted inputs shown in this evaluation"],
    [data.clean_input_count, "Original test cases", "Independent cases from the controlled laboratory"],
    [data.masked_input_count, "Missing-evidence tests", "Original cases retested with selected information hidden"],
    [data.class_order.length, "Network conditions", "One normal condition and five controlled fault types"],
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
    .map((item, index) => `<div class="method-row">
      <span class="method-index">0${index + 1}</span>
      <span><strong>${escapeHtml(labelFor(METHOD_LABELS, item))}</strong><small>${escapeHtml(METHOD_DESCRIPTIONS[item])}</small></span>
    </div>`)
    .join("");

  populateSelect("fault-filter", data.class_order, FAULT_LABELS);
  populateSelect("method-filter", data.method_order, METHOD_LABELS);

  document.getElementById("overview-boundary-text").textContent = FRIENDLY_LIMITATIONS[0];
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
    const lines = PRIMARY_METRIC_KEYS.map((key) => {
      const metric = metricDefinition(key);
      const exact = method.metrics[key];
      return `<div class="metric-line">
        <div class="metric-line-header">${metricLabelMarkup(metric)}<strong title="Exact API value: ${escapeHtml(exact)}">${escapeHtml(percent(exact))}</strong></div>
        <div class="meter" aria-hidden="true"><span style="--value: ${meterValue(exact)}%"></span></div>
      </div>`;
    }).join("");
    return `<article class="method-card">
      <div><h3>${escapeHtml(labelFor(METHOD_LABELS, method.method_id))}</h3><span class="sample-count">${escapeHtml(method.metrics.sample_count)} evaluated cases in this view</span></div>
      <div class="metric-stack">${lines}</div>
    </article>`;
  }).join("");

  document.getElementById("metric-glossary").innerHTML = METRICS.slice(0, 4)
    .map((metric) => `<div><strong>${escapeHtml(metric.label)}</strong><p>${escapeHtml(metric.description)}</p></div>`)
    .join("");

  document.getElementById("comparison-table-head").innerHTML = `<tr><th scope="col">Metric</th>${data.methods
    .map((method) => `<th scope="col">${escapeHtml(labelFor(METHOD_LABELS, method.method_id))}</th>`)
    .join("")}</tr>`;
  document.getElementById("comparison-table-body").innerHTML = METRICS.map((metric) => `<tr>
    <td><span title="${escapeHtml(metric.description)}">${escapeHtml(metric.label)}</span></td>
    ${data.methods.map((method) => `<td title="Exact API value: ${escapeHtml(method.metrics[metric.key])}">${escapeHtml(percent(method.metrics[metric.key]))}</td>`).join("")}
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

function classResult(prediction, expectedFault) {
  if (prediction.status !== "RESOLVED") {
    return { label: "No diagnosis", className: "is-neutral" };
  }
  if (prediction.predicted_fault_type === expectedFault) {
    return { label: "Correct", className: "is-correct" };
  }
  return { label: "Incorrect", className: "is-incorrect" };
}

function predictionMarkup(prediction, expectedFault) {
  const result = classResult(prediction, expectedFault);
  const diagnosis = prediction.predicted_fault_type
    ? labelFor(FAULT_LABELS, prediction.predicted_fault_type)
    : "No diagnosis";
  return `<span class="prediction-label">${escapeHtml(diagnosis)}</span>
    <span class="result-label ${result.className}">${escapeHtml(result.label)}</span>
    <span class="status-label${prediction.status === "RESOLVED" ? "" : " is-unresolved"}">${escapeHtml(statusLabel(prediction.status))}</span>`;
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
    state.innerHTML = "No evaluated cases match the selected filters.";
    return;
  }

  document.getElementById("case-table-body").innerHTML = items.map((item) => {
    const predictions = Object.fromEntries(item.predictions.map((prediction) => [prediction.method_id, prediction]));
    return `<tr>
      <td data-label="Network problem"><strong class="problem-label">${escapeHtml(labelFor(FAULT_LABELS, item.expected_fault_type))}</strong><span class="ground-truth-mini">Ground truth · evaluation only</span></td>
      <td data-label="Network scenario"><strong class="scenario-label">${escapeHtml(scenarioLabel(item))}</strong><span class="scenario-meta">${escapeHtml(topologyLabel(item.topology_id))}</span></td>
      <td data-label="Evidence"><span class="mask-label">${escapeHtml(evidenceLabel(item.mask_id))}</span></td>
      <td data-label="Rule-based" class="prediction-cell">${predictionMarkup(predictions.rule_based_p6_v1, item.expected_fault_type)}</td>
      <td data-label="Machine Learning" class="prediction-cell">${predictionMarkup(predictions.machine_learning_p6_v1, item.expected_fault_type)}</td>
      <td data-label="Hybrid" class="prediction-cell">${predictionMarkup(predictions.hybrid_p6_v1, item.expected_fault_type)}</td>
      <td data-label="Details"><button class="row-action" type="button" data-case-id="${escapeHtml(item.input_id)}" aria-label="View details for ${escapeHtml(labelFor(FAULT_LABELS, item.expected_fault_type))}; technical case ID ${escapeHtml(item.input_id)}">View</button></td>
    </tr>`;
  }).join("");

  document.getElementById("case-result-count").textContent = `${pagination.total_items} evaluated ${pagination.total_items === 1 ? "case" : "cases"}`;
  document.getElementById("case-sort").textContent = "Sorted by technical case ID · ascending";
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
  if (!diagnosis || diagnosis[key] === null || diagnosis[key] === undefined) return "Not applicable";
  return diagnosis[key];
}

function diagnosisResult(prediction, expectedDiagnosis) {
  if (prediction.status !== "RESOLVED" || !prediction.diagnosis) {
    return { label: "No diagnosis", className: "is-neutral" };
  }
  const keys = ["fault_type", "fault_category", "fault_location", "affected_prefix"];
  const exact = keys.every((key) => prediction.diagnosis[key] === expectedDiagnosis[key]);
  return exact
    ? { label: "Correct", className: "is-correct" }
    : { label: "Incorrect", className: "is-incorrect" };
}

function friendlyReason(prediction) {
  const reason = String(prediction.reason || "");
  if (reason === "Exact deterministic Phase 6 signature match.") {
    return "The available evidence exactly matched one predefined expert-rule pattern.";
  }
  if (reason === "Frozen six-class estimator argmax prediction.") {
    return `Among the six supported conditions, the frozen model assigned the highest probability to ${labelFor(FAULT_LABELS, prediction.predicted_fault_type)}.`;
  }
  if (reason === "Frozen Hybrid policy accepted the deterministic rule output.") {
    return "The Rule-based method had enough evidence, so the frozen Hybrid policy used that rule diagnosis.";
  }
  if (reason === "Rule lacked evidence; frozen policy used the ML fallback.") {
    return "The Rule-based method lacked required evidence, so the frozen Hybrid policy used the Machine Learning diagnosis.";
  }
  if (reason.startsWith("Definitive rule matching is blocked by unavailable features:")) {
    return "The strict Rule-based method did not diagnose because one or more required observations were unavailable.";
  }
  if (reason === "The ten-feature vector matches no unique frozen signature.") {
    return "The available evidence did not match exactly one predefined rule pattern, so no Rule-based diagnosis was returned.";
  }
  if (reason === "Rule and ML predictions disagree under consensus policy.") {
    return "The fixed policy withheld a diagnosis because the Rule-based and Machine Learning outputs disagreed.";
  }
  if (reason.startsWith("ML fallback met the frozen confidence threshold")) {
    return "The Rule-based method lacked evidence, and the Machine Learning fallback met the policy's fixed confidence requirement.";
  }
  if (reason.startsWith("ML fallback was below the frozen threshold")) {
    return "The Machine Learning fallback did not meet the policy's fixed confidence requirement, so the Hybrid method withheld a diagnosis.";
  }
  return "This is the accepted explanation recorded with the frozen prediction. See Technical details for the exact text.";
}

function availabilityExplanation(state) {
  const explanations = {
    observed: "Collected from the original experiment.",
    structurally_unavailable: "This observation is not defined for the current network state.",
    collection_unavailable: "The original probe could not collect this information.",
    masked_missing: "Intentionally hidden for this missing-evidence evaluation.",
  };
  return explanations[state] || "Availability state recorded by the accepted input.";
}

function evidenceValueLabel(value) {
  if (value === "true") return "Yes";
  if (value === "false") return "No";
  return "Unavailable";
}

function renderCaseDetail(data) {
  const problem = labelFor(FAULT_LABELS, data.expected_fault_type);
  document.getElementById("case-dialog-title").textContent = problem;
  document.getElementById("case-dialog-kicker").textContent = `${scenarioLabel(data)} · ${evidenceLabel(data.mask_id)}`;

  const availabilityStates = Object.values(data.evidence.availability);
  const observedCount = availabilityStates.filter((state) => state === "observed").length;
  const intentionallyHiddenCount = availabilityStates.filter((state) => state === "masked_missing").length;
  const unavailableCount = availabilityStates.length - observedCount;
  const expectedPrefix = diagnosticValue(data.expected_diagnosis, "affected_prefix");

  const summaryFields = [
    ["Traffic path", trafficPath(data.direction)],
    ["Routing checked on", nodeLabel(data.route_observer_node)],
    [data.expected_fault_type === "no_fault" ? "Destination network" : "Affected network", expectedPrefix === "Not applicable" ? data.destination_prefix : expectedPrefix],
    ["Evidence set", evidenceLabel(data.mask_id)],
  ];

  const predictions = data.predictions.map((prediction) => {
    const result = diagnosisResult(prediction, data.expected_diagnosis);
    const diagnosis = prediction.predicted_fault_type
      ? labelFor(FAULT_LABELS, prediction.predicted_fault_type)
      : "No diagnosis";
    return `<article class="prediction-detail">
      <div class="prediction-heading">
        <h4>${escapeHtml(labelFor(METHOD_LABELS, prediction.method_id))}</h4>
        <span class="result-label ${result.className}">${escapeHtml(result.label)}</span>
      </div>
      <dl>
        <dt>Diagnosis</dt><dd>${escapeHtml(diagnosis)}</dd>
        <dt>Confidence</dt><dd title="Exact API value: ${escapeHtml(prediction.confidence)}">${escapeHtml(prediction.confidence === null ? "Not provided" : percent(prediction.confidence))}</dd>
        <dt>Status</dt><dd>${escapeHtml(statusLabel(prediction.status))}</dd>
        <dt>Location</dt><dd>${escapeHtml(nodeLabel(diagnosticValue(prediction.diagnosis, "fault_location")))}</dd>
      </dl>
    </article>`;
  }).join("");

  const explanations = data.predictions.map((prediction) => `<article class="explanation-card">
    <h4>${escapeHtml(labelFor(METHOD_LABELS, prediction.method_id))}</h4>
    <p>${escapeHtml(friendlyReason(prediction))}</p>
  </article>`).join("");

  const evidence = Object.keys(FEATURE_DEFINITIONS).map((feature) => {
    const definition = FEATURE_DEFINITIONS[feature];
    const value = data.evidence.features[feature];
    const availability = data.evidence.availability[feature];
    return `<tr>
      <td><strong>${escapeHtml(definition.label)}</strong><span class="feature-description">${escapeHtml(definition.description)}</span><code class="technical-name">${escapeHtml(feature)}</code></td>
      <td><span class="evidence-value is-${escapeHtml(value)}">${escapeHtml(evidenceValueLabel(value))}</span></td>
      <td><strong class="availability-label">${escapeHtml(labelFor(AVAILABILITY_LABELS, availability))}</strong><span class="availability-description">${escapeHtml(availabilityExplanation(availability))}</span></td>
    </tr>`;
  }).join("");

  const technicalPredictions = data.predictions.map((prediction) => `<div class="technical-prediction">
    <strong>${escapeHtml(prediction.method_id)}</strong>
    <span>Status: ${escapeHtml(prediction.status)}</span>
    <span>Accepted reason: ${escapeHtml(prediction.reason)}</span>
  </div>`).join("");

  document.getElementById("case-detail-state").hidden = true;
  document.getElementById("case-detail-content").innerHTML = `
    <aside class="ground-truth-note">
      <div><span>Known ground truth — evaluation only</span><strong>${escapeHtml(problem)}</strong></div>
      <p>The known fault is shown only to evaluate whether the diagnostic methods were correct. It is not provided to the diagnostic methods as input.</p>
    </aside>
    <div class="detail-grid">${summaryFields.map(([label, value]) => `<div class="detail-field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>

    <section class="case-section" aria-labelledby="diagnostic-results-title">
      <div class="case-section-heading"><div><p class="panel-kicker">Three frozen outputs</p><h3 id="diagnostic-results-title">Diagnostic results</h3></div></div>
      <div class="prediction-detail-grid">${predictions}</div>
    </section>

    <section class="case-section explanation-section" aria-labelledby="diagnosis-explanation-title">
      <div class="case-section-heading"><div><p class="panel-kicker">Accepted reasoning in plain language</p><h3 id="diagnosis-explanation-title">Why this diagnosis?</h3></div></div>
      <p class="case-section-intro">These explanations rephrase the reasons stored with the accepted predictions. The dashboard does not run a new diagnosis.</p>
      <div class="explanation-grid">${explanations}</div>
    </section>

    <section class="evidence-panel" aria-labelledby="diagnostic-evidence-title">
      <div class="case-section-heading evidence-heading">
        <div><p class="panel-kicker">Information available to the methods</p><h3 id="diagnostic-evidence-title">Diagnostic evidence</h3></div>
        <div class="evidence-counts"><span><strong>${observedCount}</strong> of ${availabilityStates.length} available</span><span><strong>${unavailableCount}</strong> unavailable</span>${intentionallyHiddenCount ? `<span><strong>${intentionallyHiddenCount}</strong> intentionally hidden</span>` : ""}</div>
      </div>
      <div class="table-wrap">
        <table class="data-table evidence-table">
          <thead><tr><th scope="col">Diagnostic check</th><th scope="col">Result</th><th scope="col">Availability</th></tr></thead>
          <tbody>${evidence}</tbody>
        </table>
      </div>
    </section>

    <details class="technical-disclosure case-technical-details">
      <summary>Technical details</summary>
      <p class="details-helper">Internal identifiers and provenance are retained here for audit and reproducibility.</p>
      <div class="technical-grid">
        <div><span>Case ID</span><code>${escapeHtml(data.input_id)}</code></div>
        <div><span>Sample ID</span><code>${escapeHtml(data.sample_id)}</code></div>
        <div><span>Context ID</span><code>${escapeHtml(data.context_id)}</code></div>
        <div><span>Topology ID</span><code>${escapeHtml(data.topology_id)}</code></div>
        <div><span>Direction</span><code>${escapeHtml(data.direction)}</code></div>
        <div><span>Source node</span><code>${escapeHtml(data.source_node)}</code></div>
        <div><span>Route observer</span><code>${escapeHtml(data.route_observer_node)}</code></div>
        <div><span>Transit node</span><code>${escapeHtml(data.transit_node)}</code></div>
        <div><span>Destination prefix</span><code>${escapeHtml(data.destination_prefix)}</code></div>
        <div><span>Evidence mask ID</span><code>${escapeHtml(data.mask_id)}</code></div>
        <div><span>Evidence artifact</span><code>${escapeHtml(data.evidence.provenance.evidence_path)}</code></div>
        <div><span>Evidence SHA-256</span><code>${escapeHtml(data.evidence.provenance.evidence_sha256)}</code></div>
        <div><span>Dataset row SHA-256</span><code>${escapeHtml(data.evidence.provenance.dataset_row_sha256)}</code></div>
      </div>
      <div class="technical-predictions">${technicalPredictions}</div>
    </details>`;
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
    [data.projection_source_count, "Verified source files", "Every displayed result is bound to accepted source bytes"],
    ["Read-only", "Dashboard behavior", "No network change, retraining, or new inference"],
    ["Frozen", "Evaluation outputs", "Predictions and metrics are presented without recalculation"],
  ];
  document.getElementById("provenance-summary").innerHTML = cards.map(([value, label, note]) => `
    <article class="stat-card"><span class="stat-label">${escapeHtml(label)}</span><strong class="stat-value">${escapeHtml(value)}</strong><span class="stat-note">${escapeHtml(note)}</span></article>`).join("");

  const selections = `<div class="selection-metadata">
    <div><span>Selected ML candidate ID</span><code>${escapeHtml(data.selected_ml_candidate)}</code></div>
    <div><span>Selected Hybrid policy ID</span><code>${escapeHtml(data.selected_hybrid_policy)}</code></div>
  </div>`;
  const roots = data.roots.map((root) => `
    <div class="root-row">
      <strong>${escapeHtml(root.artifact_id.replaceAll("_", " "))}</strong>
      <span class="root-path">${escapeHtml(root.path)}</span>
      <span class="root-hash" title="SHA-256">${escapeHtml(root.sha256)}</span>
    </div>`).join("");
  document.getElementById("root-list").innerHTML = selections + roots;
  document.getElementById("limitations-list").innerHTML = data.limitations
    .map((limitation, index) => `<li title="Accepted source wording: ${escapeHtml(limitation)}">${escapeHtml(FRIENDLY_LIMITATIONS[index] || limitation)}</li>`)
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
    text.textContent = `Verified results · ${data.projection_source_count}/15 sources`;
  } catch (error) {
    status.className = "service-status is-error";
    text.textContent = "Accepted results unavailable";
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

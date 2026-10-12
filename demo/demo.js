"use strict";

const apiBaseInput = document.querySelector("#api-base");
const tokenInput = document.querySelector("#id-token");
const healthButton = document.querySelector("#health-button");
const healthOutput = document.querySelector("#health");
const pricingForm = document.querySelector("#pricing-form");
const quoteButton = document.querySelector("#quote-button");
const statusOutput = document.querySelector("#status");
const resultSection = document.querySelector("#result");
const resultSummary = document.querySelector("#result-summary");
const peerSummary = document.querySelector("#peer-summary");
const peerList = document.querySelector("#peers");
const reasonOutput = document.querySelector("#reason");
const competitivenessInput = document.querySelector("#competitiveness");
const competitivenessValue = document.querySelector("#competitiveness-value");

competitivenessInput.addEventListener("input", () => {
  competitivenessValue.value = Number(competitivenessInput.value).toFixed(2);
});

function resolveApiOrigin() {
  const url = new URL(apiBaseInput.value.trim());
  const host = url.hostname.replace(/^\[|\]$/g, "");
  const isLoopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
  if ((url.protocol !== "https:" && !(url.protocol === "http:" && isLoopback)) ||
      url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("Use an HTTPS API origin; plain HTTP is allowed only for localhost loopback.");
  }
  return url.origin;
}

async function readResponse(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function describeError(response, body) {
  const detail = body && typeof body === "object" ? body.detail : null;
  const message = Array.isArray(detail)
    ? detail.map((item) => `${(item.loc || []).join(".")}: ${item.msg || "invalid value"}`).join("; ")
    : typeof detail === "string" ? detail : `HTTP ${response.status}`;
  const guidance = {
    401: "Sign in again and use a fresh Firebase ID token.",
    403: "The token does not own the selected mentor profile.",
    422: "Review the request fields and try again.",
    503: "The protected pricing service or its data is unavailable.",
  }[response.status] || "Check the API response and try again.";
  return `${message} ${guidance}`;
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20_000);
  try {
    const response = await fetch(new URL(path, resolveApiOrigin()), {
      ...options,
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      signal: controller.signal,
    });
    const body = await readResponse(response);
    if (!response.ok) throw new Error(describeError(response, body));
    if (!body || typeof body !== "object") throw new Error("The API returned an unreadable response.");
    return body;
  } finally {
    window.clearTimeout(timeout);
  }
}

function formatRate(value) {
  const rate = Number(value);
  if (!Number.isFinite(rate)) return "Unavailable";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(rate)} KES/hour`;
}

function addResultRow(label, value) {
  const row = document.createElement("p");
  row.className = "result-row";
  const heading = document.createElement("strong");
  heading.textContent = `${label}: `;
  row.append(heading, document.createTextNode(value));
  resultSummary.append(row);
}

function showQuote(quote) {
  resultSummary.replaceChildren();
  peerList.replaceChildren();
  addResultRow("Final quoted rate", formatRate(quote.finalQuotedRate));
  addResultRow(
    "Negotiation corridor (excludes M-Pesa)",
    `${formatRate(quote.minQuotedRate)} – ${formatRate(quote.maxQuotedRate)}`,
  );
  addResultRow("M-Pesa transfer fee", formatRate(quote.mpesaTariffSurcharge));
  addResultRow("Base predicted rate", formatRate(quote.basePredictedRate));
  addResultRow(
    "Confidence (uncalibrated)",
    `${(Number(quote.confidenceScore) * 100).toFixed(0)}%; not a probability of accuracy`,
  );
  addResultRow("Indexed neighbors used", String(quote.kNeighborsUsed));

  const peers = Array.isArray(quote.comparables) ? quote.comparables : [];
  peerSummary.textContent = peers.length
    ? `Showing ${peers.length} listing-backed comparable(s).`
    : "No listing-backed comparables are available for this quote.";
  for (const peer of peers) {
    const item = document.createElement("article");
    item.className = "peer";
    const title = document.createElement("strong");
    title.textContent = peer.jobTitle || "Untitled listing";
    const details = document.createElement("p");
    details.textContent =
      `Listing ID: ${peer.listingId || "Unavailable"} · ` +
      `${formatRate(peer.verifiedRate)} · ` +
      `Similarity: ${(Number(peer.similarityScore) * 100).toFixed(0)}%`;
    item.append(title, details);
    peerList.append(item);
  }
  reasonOutput.textContent = typeof quote.reason === "string" ? quote.reason : "";
  resultSection.hidden = false;
}

healthButton.addEventListener("click", async () => {
  healthButton.disabled = true;
  healthOutput.textContent = "Checking API health…";
  try {
    const health = await request("/health", { headers: { Accept: "application/json" } });
    healthOutput.textContent =
      `Status: ${health.status || "unknown"}; models loaded: ${Boolean(health.modelsLoaded)}; ` +
      `repository: ${health.database || "unknown"}.`;
  } catch (error) {
    healthOutput.textContent = error instanceof Error
      ? `${error.message} Check the API origin and its explicit CORS allow-list.`
      : "Unable to reach the API. Check the API origin and its CORS allow-list.";
  } finally {
    healthButton.disabled = false;
  }
});

pricingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  quoteButton.disabled = true;
  statusOutput.textContent = "Checking protected API readiness…";
  resultSection.hidden = true;
  const token = tokenInput.value.trim();
  try {
    if (!token) throw new Error("A temporary Firebase ID token is required.");
    const health = await request("/health", { headers: { Accept: "application/json" } });
    if (health.status !== "HEALTHY" || health.database !== "firestore" || health.modelsLoaded !== true) {
      throw new Error("Quote blocked: this demo requires the healthy Firebase-protected Firestore API.");
    }

    statusOutput.textContent = "Requesting quote…";
    const body = {
      mentorId: document.querySelector("#mentor-id").value.trim(),
      rawText: document.querySelector("#service-description").value.trim(),
      industry: document.querySelector("#industry").value,
      mentorCountry: document.querySelector("#mentor-country").value.trim().toUpperCase(),
      clientCountry: document.querySelector("#client-country").value.trim().toUpperCase(),
      competitivenessScore: Number(competitivenessInput.value),
    };
    const floor = document.querySelector("#base-rate-floor").value;
    if (floor !== "") body.baseRateFloor = Number(floor);
    const quote = await request("/api/v1/optimize-price", {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    showQuote(quote);
    statusOutput.textContent = "Protected pricing request completed.";
  } catch (error) {
    statusOutput.textContent = error instanceof Error
      ? `${error.message} A browser network error may also mean the API origin is not CORS-allow-listed.`
      : "Unable to complete the request. Check the API origin and CORS allow-list.";
  } finally {
    tokenInput.value = "";
    quoteButton.disabled = false;
  }
});

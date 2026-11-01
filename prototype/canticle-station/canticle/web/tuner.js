// Canticle human-facing metadata dashboard.
// Read-only: this page consumes only /api/stations and never exposes item payloads.
"use strict";

const STATIONS_MS = 2000;

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("data-") || k.startsWith("aria-") || k === "role" || k === "type") e.setAttribute(k, v);
    else e[k] = v;
  }
  for (const kid of kids) e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return e;
}

function secs(ms) {
  return (ms / 1000).toFixed(ms < 10000 ? 1 : 0) + " s";
}

async function api(path) {
  const r = await fetch(path);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.error || r.statusText), {status: r.status});
  return data;
}

async function refreshStations() {
  const box = document.getElementById("stations");
  const status = document.getElementById("stations-status");
  try {
    const s = await api("/api/stations");
    box.replaceChildren();
    status.textContent = s.stations.length ? "" : "Waiting for a verified beacon…";
    for (const st of s.stations) {
      const beaconClass = st.beacon_active ? "ok" : "stale";
      const card = el("div", {class: "station", "data-testid": "station", "data-station": st.name},
        el("h3", {}, st.name,
          el("span", {class: "badge ok"}, "verified"),
          el("span", {class: "badge " + beaconClass}, st.beacon_active ? "beacon active" : "beacon inactive")),
        el("div", {class: "kv"},
          `presence ${st.presence} · epoch ${st.epoch} · key ${st.key_id}`),
        el("div", {class: "kv"},
          `lease ${st.lease_active ? "active" : "inactive"} · remaining ${secs(st.lease_remaining_ms)} · ` +
          `last beacon ${secs(st.beacon_age_ms)} ago`));

      const table = el("table", {},
        el("thead", {}, el("tr", {}, el("th", {}, "public stream"), el("th", {}, "health"),
          el("th", {}, "head"), el("th", {}, "live"), el("th", {}, "TTL / lease"), el("th", {}, "loop")))),
        el("tbody"));
      for (const sm of st.streams) {
        table.tBodies[0].append(el("tr", {"data-testid": "stream", "data-stream": sm.name},
          el("td", {}, sm.name),
          el("td", {class: "health " + sm.health}, sm.health),
          el("td", {class: "num"}, String(sm.head_seq)),
          el("td", {class: "num"}, String(sm.live)),
          el("td", {}, `TTL ${sm.ttl_s}s / lease ${sm.lease_active ? secs(sm.lease_remaining_ms) : "inactive"}`),
          el("td", {class: "num"}, secs(sm.loop_ms))));
      }
      card.append(table);
      box.append(card);
    }
    const bad = Object.entries(s.unverified_datagrams || {}).map(([k, v]) => `${k} ${v}`).join(", ");
    document.getElementById("unverified").textContent =
      "Unverified datagrams (counted, never shown): " + (bad || "none");
  } catch (e) {
    status.textContent = "Gateway unreachable: " + e.message;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  refreshStations();
  setInterval(refreshStations, STATIONS_MS);
});

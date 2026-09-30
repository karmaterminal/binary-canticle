// Canticle tuner page. Read-only: it asks the loopback gateway what its listener holds.
// Heard text is data: it is only ever set with textContent, never parsed as markup.
"use strict";

const STATIONS_MS = 2000;
const RING_MS = 1000;
let sub = null;          // {id, station, stream, label}
let ringTimer = null;

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

function utc(ms) { return new Date(ms).toISOString().slice(11, 19) + " UTC"; }
function secs(ms) { return (ms / 1000).toFixed(ms < 10000 ? 1 : 0) + " s"; }

function presenceText(state, lastBeacon) {
  if (state === "UNOBSERVABLE:signed_off") return "signed off at " + utc(lastBeacon);
  if (state === "UNOBSERVABLE") return lastBeacon ? "not observable since " + utc(lastBeacon) : "not observable";
  return state.toLowerCase().replace(/_/g, " ");
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)};
  const r = await fetch(path, opts);
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
      const fresh = !st.presence.startsWith("UNOBSERVABLE");
      const card = el("div", {class: "station", "data-testid": "station", "data-station": st.name},
        el("h3", {}, st.name,
          el("span", {class: "badge ok"}, "verified"),
          el("span", {class: "badge" + (fresh ? "" : " stale")}, presenceText(st.presence, st.last_beacon_ms))),
        el("div", {class: "kv"}, `key ${st.key_id} · epoch ${st.epoch} · last beacon ${secs(st.beacon_age_ms)} ago` +
          (st.beacon_period_ms ? ` (every ${secs(st.beacon_period_ms)})` : "")));
      const table = el("table", {},
        el("thead", {}, el("tr", {}, el("th", {}, "stream"), el("th", {}, "head"), el("th", {}, "live"),
          el("th", {}, "loop"), el("th", {}, ""))));
      const tb = el("tbody");
      for (const sm of st.streams) {
        const label = sm.name || ("unnamed 0x" + sm.stream_id);
        const btn = el("button", {type: "button", "data-testid": `tune-${st.name}-${label}`,
          "aria-label": `tune ${st.name}:${label}`}, "Tune");
        btn.disabled = !sm.tunable;
        if (!sm.tunable) btn.title = "Not named in the manifest: verified but not shown (RFC-0001 §5.4)";
        btn.addEventListener("click", () => tune(st, sm, label));
        tb.append(el("tr", {}, el("td", {}, label), el("td", {class: "num"}, sm.head_seq),
          el("td", {class: "num"}, sm.live), el("td", {class: "num"}, secs(sm.loop_ms)), el("td", {}, btn)));
      }
      table.append(tb);
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

async function leave() {
  if (ringTimer) { clearInterval(ringTimer); ringTimer = null; }
  if (sub) {
    const id = sub.id;
    sub = null;
    await api("/api/leave", {sub: id}).catch(() => {});
  }
  document.getElementById("tuned").replaceChildren(el("p", {class: "muted", "data-testid": "not-tuned"},
    "Not tuned. Pick a named stream on the left."));
}

async function tune(st, sm, label) {
  await leave();
  try {
    const r = await api("/api/tune", {station: st.key_id, stream: sm.stream_id});
    sub = {id: r.sub, label: `${st.name}:${label}`};
    await refreshRing();
    ringTimer = setInterval(refreshRing, RING_MS);
  } catch (e) {
    document.getElementById("tuned").replaceChildren(el("p", {class: "muted"}, "Could not tune: " + e.message));
  }
}

async function refreshRing() {
  if (!sub) return;
  const box = document.getElementById("tuned");
  let r;
  try {
    r = await api("/api/ring?sub=" + encodeURIComponent(sub.id));
  } catch (e) {
    if (e.status === 429) return;
    if (e.status === 404) {
      sub = null;
      clearInterval(ringTimer); ringTimer = null;
      box.replaceChildren(el("p", {class: "muted"}, "Tuning lapsed (idle or gateway restarted). Tune again."));
    }
    return;
  }
  const leaveBtn = el("button", {type: "button", "data-testid": "leave"}, "Leave");
  leaveBtn.addEventListener("click", leave);
  const head = el("div", {class: "ring-head"},
    el("h3", {"data-testid": "tuned-channel"}, sub.label),
    el("span", {class: "kv"}, `${presenceText(r.presence, null)} · head ${r.head_seq ?? "?"} · ` +
      `station says ${r.live_advertised ?? "?"} live · loop ${r.loop_ms ? secs(r.loop_ms) : "?"}`),
    leaveBtn);
  const items = el("div", {"data-testid": "ring"});
  if (!r.items.length) items.append(el("p", {class: "muted", "data-testid": "ring-empty"}, "Nothing on air that this listener holds."));
  for (const it of r.items) {
    const span = Math.max(1, it.local_expiry_ms - it.first_heard_ms);
    const bar = el("div");
    bar.style.width = Math.max(0, Math.min(100, 100 * it.remaining_ms / span)).toFixed(1) + "%";
    items.append(el("div", {class: "item", "data-testid": "item", "data-seq": String(it.seq)},
      el("div", {class: "text"}, it.text !== undefined ? it.text + (it.truncated ? " …" : "")
        : `(binary, ${it.binary_bytes} bytes)`),
      el("div", {class: "meta"}, `seq ${it.seq} · ${it.class} · heard ${it.copies}× · issued ${utc(it.issued_at)} · ` +
        `expires in ${secs(it.remaining_ms)}`),
      el("div", {class: "life", "aria-hidden": "true"}, bar)));
  }
  const tombs = el("div", {"data-testid": "tombstones"});
  for (const t of r.tombstones) {
    const why = t.reason === "withdrawn" ? `withdrawn by seq ${t.by_seq}` :
      t.reason === "superseded" ? `superseded by seq ${t.by_seq}` : "expired";
    tombs.append(el("div", {class: "tomb", "data-testid": "tomb", "data-seq": String(t.seq)},
      `seq ${t.seq} ${why} at ${utc(t.at_ms)} (no longer on air)`));
  }
  const gaps = r.unheard_seq.length
    ? `Not heard by this gateway: seq ${r.unheard_seq.slice(0, 20).join(", ")}${r.unheard_seq.length > 20 ? " …" : ""}.`
    : "No gaps below the head.";
  box.replaceChildren(head, items, tombs,
    el("p", {class: "note", "data-testid": "gaps"}, gaps),
    el("p", {class: "note"}, r.note));
}

document.addEventListener("DOMContentLoaded", () => {
  refreshStations();
  setInterval(refreshStations, STATIONS_MS);
  window.addEventListener("pagehide", () => {
    if (sub) fetch("/api/leave", {method: "POST", keepalive: true,
      headers: {"Content-Type": "application/json"}, body: JSON.stringify({sub: sub.id})}).catch(() => {});
  });
});

"""Build figures/e1-p99.html from prototype/protocol-dynamics/results/e1_freshness.json.

Small multiples, one per update interval: p99 update latency (log scale) against
packet loss (both directions) for the canticle carousel (udp-live, 5 s loop) and
a TCP stream. Series colours are the dataviz reference slots 1-2, validated
against this page's light and dark surfaces.

    python reports/page/figures/make_e1_p99.py
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "prototype/protocol-dynamics/results/e1_freshness.json"
OUT = HERE / "e1-p99.html"

ARMS = [("udp-live", "Carousel (UDP)", "c"), ("tcp-stream", "TCP stream", "t")]
INTERVALS = [0.5, 2.0, 10.0]
LOSSES = [0, 10, 50, 100, 200, 300]  # per mille

W, H = 300, 230
ML, MR, MT, MB = 50, 78, 12, 34
PW, PH = W - ML - MR, H - MT - MB
Y_MIN, Y_MAX = 0.0, 6.0  # log10(ms): 1 ms .. 1000 s
TICKS = [(0, "1 ms"), (1, "10 ms"), (2, "100 ms"), (3, "1 s"), (4, "10 s"), (5, "100 s"), (6, "1000 s")]


def fmt(ms: float) -> str:
    if ms >= 10_000:
        return f"{ms / 1000:,.0f} s"
    if ms >= 1000:
        return f"{ms / 1000:.1f} s"
    return f"{ms:,.0f} ms" if ms >= 10 else f"{ms:.1f} ms"


def x_at(i: int) -> float:
    return ML + PW * i / (len(LOSSES) - 1)


def y_at(ms: float) -> float:
    v = min(max(math.log10(max(ms, 1.0)), Y_MIN), Y_MAX)
    return MT + PH * (1 - (v - Y_MIN) / (Y_MAX - Y_MIN))


def panel(rows: dict, u: float) -> str:
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="p99 update latency against loss, updates every {u:g} s">']
    for v, label in TICKS:
        y = y_at(10 ** v)
        parts.append(f'<line class="g" x1="{ML}" x2="{ML + PW}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="yt" x="{ML - 6}" y="{y + 3.5:.1f}">{label}</text>')
    for i, pm in enumerate(LOSSES):
        parts.append(f'<text class="xt" x="{x_at(i):.1f}" y="{MT + PH + 16}">{pm // 10}</text>')
    parts.append(f'<text class="xl" x="{ML + PW / 2:.1f}" y="{H - 3}">packet loss, % (both directions)</text>')
    ends = []
    for arm, name, key in ARMS:
        pts = [(x_at(i), y_at(rows[(u, pm, arm)]), rows[(u, pm, arm)], pm) for i, pm in enumerate(LOSSES)]
        d = " ".join(f"{'M' if j == 0 else 'L'}{x:.1f},{y:.1f}" for j, (x, y, _, _) in enumerate(pts))
        parts.append(f'<path class="ln s-{key}" d="{d}"/>')
        for x, y, ms, pm in pts:
            tip = html.escape(f"{name} · updates every {u:g} s · {pm // 10}% loss: p99 {fmt(ms)}")
            parts.append(f'<circle class="dot s-{key}" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{tip}</title></circle>')
            parts.append(f'<circle class="hit" cx="{x:.1f}" cy="{y:.1f}" r="11" data-tip="{tip}" tabindex="0"/>')
        ends.append([pts[-1][1], name, key])
    if abs(ends[0][0] - ends[1][0]) < 14:  # keep end labels from colliding
        lo, hi = sorted(ends, key=lambda e: e[0])
        lo[0], hi[0] = lo[0] - 7, hi[0] + 7
    for y, name, key in ends:
        parts.append(f'<line class="key s-{key}" x1="{ML + PW + 6}" x2="{ML + PW + 14}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="el" x="{ML + PW + 17}" y="{y + 3.5:.1f}">{html.escape(name.split(" (")[0])}</text>')
    parts.append("</svg>")
    return f'<figure class="p"><figcaption>Updates every {u:g} s</figcaption>{"".join(parts)}</figure>'


def main() -> None:
    rows = {}
    for r in json.loads(DATA.read_text())["rows"]:
        if r["loss_direction"] == "both" and r["outage_s"] == 0:
            rows[(r["update_s"], r["loss_permille"], r["arm"])] = r["update_latency_ms"]["p99"]
    panels = "".join(panel(rows, u) for u in INTERVALS)
    OUT.write_text(f"""<div class="viz-e1">
<style>
.viz-e1 {{ --s-c: #2a78d6; --s-t: #eb6834; margin: 18px 0 8px; }}
@media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) .viz-e1 {{ --s-c: #3987e5; --s-t: #d95926; }} }}
:root[data-theme="dark"] .viz-e1 {{ --s-c: #3987e5; --s-t: #d95926; }}
.viz-e1 .hd {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 18px; align-items: baseline; }}
.viz-e1 .hd strong {{ font-size: 15px; }}
.viz-e1 .lg {{ display: flex; gap: 14px; font-size: 13px; color: var(--ink-2); }}
.viz-e1 .lg span {{ display: inline-flex; align-items: center; gap: 6px; }}
.viz-e1 .lg i {{ width: 16px; height: 2px; display: inline-block; }}
.viz-e1 .sub {{ margin: 2px 0 8px; font-size: 13px; color: var(--ink-2); max-width: none; }}
.viz-e1 .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; position: relative; }}
@media (max-width: 760px) {{ .viz-e1 .grid {{ grid-template-columns: minmax(0, 1fr); }} }}
.viz-e1 figure.p {{ margin: 0; border: 1px solid var(--rule); border-radius: 4px; background: var(--paper-2); padding: 6px 4px 2px; }}
.viz-e1 figcaption {{ font-size: 12.5px; font-weight: 600; padding: 0 6px; }}
.viz-e1 svg {{ display: block; width: 100%; height: auto; overflow: visible; }}
.viz-e1 .g {{ stroke: var(--rule); stroke-width: 1; }}
.viz-e1 .yt {{ fill: var(--ink-2); font: 10px var(--mono); text-anchor: end; }}
.viz-e1 .xt {{ fill: var(--ink-2); font: 10px var(--mono); text-anchor: middle; }}
.viz-e1 .xl {{ fill: var(--ink-2); font: 10px var(--sans); text-anchor: middle; }}
.viz-e1 .el {{ fill: var(--ink); font: 600 10.5px var(--sans); }}
.viz-e1 .ln {{ fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }}
.viz-e1 .dot {{ stroke: var(--paper-2); stroke-width: 2; }}
.viz-e1 .key {{ stroke-width: 2; }}
.viz-e1 .s-c {{ stroke: var(--s-c); }} .viz-e1 .dot.s-c, .viz-e1 i.s-c {{ fill: var(--s-c); background: var(--s-c); }}
.viz-e1 .s-t {{ stroke: var(--s-t); }} .viz-e1 .dot.s-t, .viz-e1 i.s-t {{ fill: var(--s-t); background: var(--s-t); }}
.viz-e1 .hit {{ fill: transparent; cursor: default; }}
.viz-e1 .hit:focus-visible {{ outline: none; stroke: var(--focus); stroke-width: 2; }}
.viz-e1 .tip {{ position: absolute; pointer-events: none; background: var(--paper); color: var(--ink); border: 1px solid var(--rule);
  border-radius: 4px; padding: 5px 8px; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.12); white-space: nowrap; }}
</style>
<div class="hd"><strong>Worst-case staleness under packet loss</strong>
<span class="lg"><span><i class="s-c"></i>Carousel (UDP, 5 s loop)</span><span><i class="s-t"></i>TCP stream</span></span></div>
<p class="sub">p99 time from an update being issued to a receiver holding it, log scale. Measured in <code>prototype/protocol-dynamics</code> (E1): 900 s per condition, 20 receivers per arm, RTT ≈ 0.1 ms. TCP is fresher up to about 10% loss; above that its retransmission backoff runs to minutes.</p>
<div class="grid">{panels}<div class="tip" hidden></div></div>
<script>
(function () {{
  var root = document.currentScript.parentNode, grid = root.querySelector(".grid"), tip = root.querySelector(".tip");
  function show(e) {{
    var t = e.target; if (!t.dataset || !t.dataset.tip) return;
    tip.textContent = t.dataset.tip; tip.hidden = false;
    var g = grid.getBoundingClientRect(), r = t.getBoundingClientRect();
    var x = r.left - g.left + r.width / 2, y = r.top - g.top;
    tip.style.left = Math.max(0, Math.min(x - tip.offsetWidth / 2, g.width - tip.offsetWidth)) + "px";
    tip.style.top = Math.max(0, y - tip.offsetHeight - 6) + "px";
  }}
  function hide() {{ tip.hidden = true; }}
  grid.addEventListener("mouseover", show); grid.addEventListener("focusin", show);
  grid.addEventListener("mouseout", hide); grid.addEventListener("focusout", hide);
}})();
</script>
</div>
""")
    print("wrote", OUT)


if __name__ == "__main__":
    main()

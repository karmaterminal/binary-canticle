"""Static SVG line charts for the report (no dependencies): RSS over time per process, and a single
rate series over time. Light and dark are both selected (prefers-color-scheme inside the SVG).
Palette: the dataviz reference categorical slots 1-3 (validated adjacent-pair, both modes); the
light aqua slot sits under 3:1 on the light surface, so every line carries a direct end label and
the sampler CSV beside each chart is the table view.

    python plot_svg.py rss <samples.csv> <out.svg> "<title>" label[=Name] ...
    python plot_svg.py rate <result.json> <out.svg> "<title>"
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

LIGHT = ["#2a78d6", "#eb6834", "#1baf7a"]
DARK = ["#3987e5", "#d95926", "#199e70"]
W, H = 760, 340
L, R, T, B = 64, 150, 56, 44


def nice_max(v: float) -> float:
    for mag in (0.1, 1, 10, 100, 1000, 10000, 100000, 1000000):
        for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8):
            m = step * mag
            if m >= v:
                return m
    return v


def nice_step(span: float, n: int = 6) -> float:
    raw = span / n
    for mag in (1, 10, 100, 1000, 10000):
        for step in (1, 2, 2.5, 5):
            if step * mag >= raw:
                return step * mag
    return raw


def style(n: int) -> str:
    light = "".join(f".s{i}{{stroke:{c}}}.f{i}{{fill:{c}}}" for i, c in enumerate(LIGHT[:n]))
    dark = "".join(f".s{i}{{stroke:{c}}}.f{i}{{fill:{c}}}" for i, c in enumerate(DARK[:n]))
    return (f"<style>svg{{font-family:system-ui,-apple-system,Segoe UI,sans-serif}}"
            f".bg{{fill:#fcfcfb}}.t1{{fill:#0b0b0b}}.t2{{fill:#52514e}}.grid{{stroke:#e4e3df;stroke-width:1}}"
            f".axis{{stroke:#c9c8c2;stroke-width:1}}.ln{{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}"
            f".ring{{stroke:#fcfcfb;stroke-width:2}}{light}"
            f"@media (prefers-color-scheme: dark){{.bg{{fill:#1a1a19}}.t1{{fill:#f0efec}}.t2{{fill:#c3c2b7}}"
            f".grid{{stroke:#2e2e2c}}.axis{{stroke:#4a4a47}}.ring{{stroke:#1a1a19}}{dark}}}</style>")


def chart(series: list[tuple[str, list[tuple[float, float]]]], title: str, ylabel: str, xlabel: str,
          fmt=lambda v: f"{v:.0f}") -> str:
    xs = [x for _, pts in series for x, _ in pts] or [0, 1]
    ys = [y for _, pts in series for _, y in pts] or [0, 1]
    x0, x1 = 0.0, max(xs) or 1
    y1 = nice_max(max(ys) * 1.05 or 1)
    pw, ph = W - L - R, H - T - B

    def px(x):
        return L + (x - x0) / (x1 - x0) * pw

    def py(y):
        return T + ph - y / y1 * ph

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="{title}">', style(len(series)), f'<rect class="bg" width="{W}" height="{H}"/>',
           f'<text class="t1" x="{L}" y="22" font-size="15" font-weight="600">{title}</text>']
    # legend, one row under the title
    lx = L
    for i, (name, _) in enumerate(series if len(series) > 1 else []):   # one series: the title names it
        out.append(f'<line class="ln s{i}" x1="{lx}" y1="40" x2="{lx + 18}" y2="40"/>')
        out.append(f'<text class="t2" x="{lx + 24}" y="44" font-size="12">{name}</text>')
        lx += 24 + 7.2 * len(name) + 22
    for k in range(5):
        v = y1 * k / 4
        y = py(v)
        out.append(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}"/>')
        out.append(f'<text class="t2" x="{L - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end">{fmt(v)}</text>')
    xs_step = nice_step(x1 - x0)
    for k in range(int((x1 - x0) // xs_step) + 1):
        v = x0 + k * xs_step
        out.append(f'<text class="t2" x="{px(v):.1f}" y="{T + ph + 18}" font-size="11" text-anchor="middle">{v:.0f}</text>')
    out.append(f'<line class="axis" x1="{L}" y1="{T + ph}" x2="{L + pw}" y2="{T + ph}"/>')
    out.append(f'<text class="t2" x="{L + pw / 2}" y="{H - 6}" font-size="12" text-anchor="middle">{xlabel}</text>')
    out.append(f'<text class="t2" x="14" y="{T + ph / 2}" font-size="12" text-anchor="middle" '
               f'transform="rotate(-90 14 {T + ph / 2})">{ylabel}</text>')
    ends = []
    for i, (name, pts) in enumerate(series):
        if not pts:
            continue
        step = max(1, len(pts) // 600)
        thin = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
        d = " ".join(f"{'M' if j == 0 else 'L'}{px(x):.1f},{py(y):.1f}" for j, (x, y) in enumerate(thin))
        out.append(f'<path class="ln s{i}" d="{d}"/>')
        ends.append([py(pts[-1][1]), i, name, pts[-1][1]])
    # direct end labels with leader lines, nudged apart only in the label column
    ends.sort()
    for j in range(1, len(ends)):
        ends[j][0] = max(ends[j][0], ends[j - 1][0] + 15)
    for y_lab, i, name, v in ends:
        y_pt = py(series[i][1][-1][1])
        x_end = px(series[i][1][-1][0])
        out.append(f'<circle class="f{i} ring" cx="{x_end:.1f}" cy="{y_pt:.1f}" r="4"/>')
        out.append(f'<line class="axis" x1="{x_end + 6:.1f}" y1="{y_pt:.1f}" x2="{L + pw + 10}" y2="{y_lab:.1f}"/>')
        label = f"{name} {fmt(v)}" if len(series) > 1 else fmt(v)
        out.append(f'<text class="t1" x="{L + pw + 14}" y="{y_lab + 4:.1f}" font-size="12">{label}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    kind = sys.argv[1]
    if kind == "rss":
        src, dst, title = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
        want = []
        for spec in sys.argv[5:]:
            label, _, name = spec.partition("=")
            want.append((label, name or label))
        pts: dict[str, list] = {label: [] for label, _ in want}
        with open(src) as f:
            for row in csv.DictReader(f):
                if row["label"] in pts:
                    pts[row["label"]].append((float(row["t_s"]), int(row["rss_kb"]) / 1024))
        series = [(name, pts[label]) for label, name in want]
        dst.write_text(chart(series, title, "RSS (MiB)", "seconds since the lab started"))
    elif kind == "rate":
        src, dst, title = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
        r = json.loads(src.read_text())
        per = r["probe_verified_per_s"]
        series = [("verified frame records / s", [(i - 1 + 0.5, v) for i, v in enumerate(per)])]
        dst.write_text(chart(series, title, "records / s", "seconds since the producers started"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Render a report's markdown into a self-contained HTML page.

    python reports/page/build.py reports/2026-09-27-survey-and-path.md out.html [--ref BRANCH]

- Repository citations in backticks (`path` or `path:line`) link to GitHub:
  files that exist at the report's baseline commit link there (the line numbers
  were checked against it); files added later link to ``--ref``.
- `#N` issue and PR references link to the repository.
- A paragraph that is exactly ``@@FIGURE:name@@`` is replaced by the HTML in
  ``reports/page/figures/name.html`` (charts and other inline figures).

Needs ``markdown-it-py`` and ``mdit-py-plugins``.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
REPO = "https://github.com/karmaterminal/binary-canticle"
BASE_SHA = "b46a45a"  # the commit the report's path:line citations were checked against
LABELS = {"V": "verified", "I": "inferred", "R": "recommendation", "S": "search excerpt"}


def git_files(ref: str) -> set[str]:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", ref],
                         capture_output=True, text=True, check=True).stdout
    return set(out.split())


def render(source: Path, ref: str) -> str:
    base_files = git_files(BASE_SHA)
    branch_files = set(subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files"],
                                      capture_output=True, text=True, check=True).stdout.split())

    md = (MarkdownIt("commonmark", {"html": False})
          .enable("table").enable("strikethrough")
          .use(anchors_plugin, max_level=3, permalink=False))

    text = source.read_text()
    title_match = re.match(r"# (.+)\n", text)
    body_md = text[title_match.end():] if title_match else text
    pre, sep, rest = body_md.partition("\n---\n")
    preamble_md, body_md = (pre, rest) if sep else ("", body_md)

    def link_code(m):
        inner = m.group(1)
        cm = re.match(r"^([\w./-]+?)(?::(\d+)(?:-(\d+))?)?(?:[,:].*)?$", html.unescape(inner))
        if not cm:
            return m.group(0)
        path, l1, l2 = cm.group(1).rstrip("/"), cm.group(2), cm.group(3)
        if path in base_files or any(f.startswith(path + "/") for f in base_files):
            at, known = BASE_SHA, base_files
        elif path in branch_files or any(f.startswith(path + "/") for f in branch_files):
            at, known = ref, branch_files
        else:
            return m.group(0)
        kind = "blob" if path in known else "tree"
        anchor = ""
        if l1 and kind == "blob":
            anchor = f"#L{l1}" + (f"-L{l2}" if l2 else "")
            if path.endswith(".md"):
                anchor = "?plain=1" + anchor
        return f'<a class="cite" href="{REPO}/{kind}/{at}/{path}{anchor}"><code>{inner}</code></a>'

    def text_nodes(t):
        t = re.sub(r"\[(V|I|R|S)\]",
                   lambda m: f'<span class="lbl lbl-{m.group(1)}" title="{LABELS[m.group(1)]}">{m.group(1)}</span>', t)
        return re.sub(r"(?<![\w/&])#(\d{1,3})\b",
                      lambda m: f'<a class="iss" href="{REPO}/issues/{m.group(1)}">#{m.group(1)}</a>', t)

    def decorate(h):
        h = re.sub(r"<code>([^<]+)</code>", link_code, h)
        out, i = [], 0
        for m in re.finditer(r"(<code>.*?</code>|<a [^>]*>.*?</a>|<[^>]+>)", h, re.S):
            out.append(text_nodes(h[i:m.start()]))
            out.append(m.group(0))
            i = m.end()
        out.append(text_nodes(h[i:]))
        h = "".join(out)
        h = h.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
        return re.sub(r"<p>@@FIGURE:([\w-]+)@@</p>",
                      lambda m: (HERE / "figures" / f"{m.group(1)}.html").read_text(), h)

    body_html = decorate(md.render(body_md))
    preamble_html = decorate(md.render(preamble_md))
    toc = []
    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body_html):
        label = re.sub(r"<[^>]+>", "", m.group(2))
        num, _, name = label.partition(". ")
        toc.append((m.group(1), num if name else "", name or label))
    toc_html = "\n".join(f'<li><a href="#{i}"><span class="n">{html.escape(n)}</span>{html.escape(name)}</a></li>'
                         for i, n, name in toc)
    rel = source.resolve().relative_to(REPO_ROOT).as_posix()
    return ((HERE / "template.html").read_text()
            .replace("{{PREAMBLE}}", preamble_html).replace("{{TOC}}", toc_html).replace("{{BODY}}", body_html)
            .replace("{{REPO}}", REPO).replace("{{BRANCH}}", ref).replace("{{SOURCE}}", rel))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--ref", default="main", help="git ref that files added after the baseline link to")
    a = ap.parse_args()
    page = render(a.source, a.ref)
    a.out.write_text(page)
    print(f"wrote {a.out} ({len(page)} bytes)")


if __name__ == "__main__":
    main()

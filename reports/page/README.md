# Report page generator

Builds the designed HTML view of a report in `reports/` (the same page published
as a claude.ai artifact). The markdown in `reports/` is the source of truth; the
page is a rendering of it.

```sh
python3 -m venv .venv && .venv/bin/pip install markdown-it-py mdit-py-plugins
.venv/bin/python reports/page/build.py reports/2026-09-27-survey-and-path.md /tmp/survey.html --ref main
```

- `template.html` holds the page design: a light "seismograph paper" theme and a
  dark console theme, a sticky contents list, a carrier-trace header (an
  illustration, not data), recommendation chips and a filter on long triage tables.
- `figures/<name>.html` holds inline figures. A report paragraph containing only
  `@@FIGURE:<name>@@` is replaced by that file.
- `--ref` is the branch or commit that files added after the report's baseline
  (`b46a45a`) link to. Citations into files that existed at the baseline link to
  `b46a45a`, because their line numbers were checked there.

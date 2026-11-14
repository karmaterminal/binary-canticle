# Same-host proof: ambient emitter and synthetic-only human dashboard

A bounded run of the ambient emitter, the agent-only listeners and the human dashboard. The dashboard
does not expose listener observations. It displays one explicitly labelled synthetic fixture station.

**This is same-host evidence.** The station and listener sides run in two network namespaces on one
kernel, joined by a veth pair. It is not a second host.

## Run

```sh
sudo PYTHON=/path/to/python-with-cryptography ./run.sh
python3 analyze.py results/<UTC stamp>
```

`run.sh` needs root and network namespaces. `browser.cjs` needs Node with Playwright and Chromium.

The proof lane uses:

- `snapshots.py`: polls only `GET /api/stations` and records synthetic/fixture counts.
- `browser.cjs`: verifies the synthetic station and stream DOM and rejects item/ring/tune elements.
- `analyze.py`: keeps the listener and emission evidence, but does not treat dashboard snapshots as
  live station evidence.

The `canticle tuner` process is started with `--demo-fixture`. It has no `--log` option: listener events,
item text, bodies, findings, body references and state/dedup digests are never written as tuner logs.

## What the lane proves

- The emitter and early/late listeners still show normal signed-item emission and hearing behavior.
- The station still receives no UDP datagrams; it has no subscriber table or acknowledgement loop.
- The dashboard's HTTP surface contains only `GET /` and `GET /api/stations`.
- The dashboard has no ring, tune or leave controls, and the browser DOM has no item or ring payload.
- A synthetic fixture is independent of verified live listener state and contains no real station metadata.

## What it does not prove

- A second host or a wide-area network path.
- Human consent or policy approval for future live station disclosure.
- Session landing, which remains outside this spike.

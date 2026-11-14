// Drive the synthetic-only human dashboard in headless Chromium. One JSON line per step on stdout.
//   node browser.cjs early|late|drain <results-dir>
"use strict";
const {chromium} = require("playwright");
const path = require("path");

const URL = "http://127.0.0.1:8765/";
const [phase, out] = process.argv.slice(2);

function emit(step, data) {
  process.stdout.write(JSON.stringify({t_ms: Date.now(), phase, step, ...data}) + "\n");
}

async function dashboard(page) {
  return page.evaluate(() => ({
    status: document.getElementById("stations-status")?.textContent ?? null,
    stations: [...document.querySelectorAll('[data-testid="station"]')].map(e => ({
      name: e.querySelector("h3")?.childNodes[0]?.textContent?.trim() ?? null,
      synthetic: [...e.querySelectorAll(".badge")].some(b => b.textContent === "synthetic fixture")
    })),
    streams: [...document.querySelectorAll('[data-testid="stream"]')].map(e => e.dataset.stream),
    payloadElements: document.querySelectorAll('[data-testid="item"], [data-testid="ring"], [data-testid="tuned-channel"]').length,
  }));
}

async function shot(page, name) {
  await page.screenshot({path: path.join(out, name), fullPage: true});
  emit("screenshot", {file: name});
}

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({viewport: {width: 1180, height: 820}})).newPage();
  const consoleErrors = [];
  page.on("console", m => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", e => consoleErrors.push(String(e)));
  await page.goto(URL);
  await page.getByTestId("station").waitFor({timeout: 15000});
  await page.waitForTimeout(500);
  emit("loaded", {dashboard: await dashboard(page)});
  await shot(page, `0-${phase}-synthetic.png`);
  await page.waitForTimeout(1500);
  emit("verified", {dashboard: await dashboard(page)});
  emit("done", {console_errors: consoleErrors});
  await browser.close();
})().catch(e => { emit("error", {error: String(e)}); process.exit(1); });

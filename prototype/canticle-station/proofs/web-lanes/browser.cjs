// Drive the tuner page in headless Chromium for the #57 proof. One JSON line per step on stdout.
//   node browser.cjs early|late|drain <results-dir>
"use strict";
const {chromium} = require("playwright");
const path = require("path");

const URL = "http://127.0.0.1:8765/";
const [phase, out] = process.argv.slice(2);
const STATION = "hymn-room";

function emit(step, data) {
  process.stdout.write(JSON.stringify({t_ms: Date.now(), phase, step, ...data}) + "\n");
}

async function ring(page) {
  return page.evaluate(() => ({
    channel: document.querySelector('[data-testid="tuned-channel"]')?.textContent ?? null,
    items: [...document.querySelectorAll('[data-testid="item"]')].map(e => ({
      seq: Number(e.dataset.seq), text: e.querySelector(".text").textContent,
      meta: e.querySelector(".meta").textContent})),
    tombstones: [...document.querySelectorAll('[data-testid="tomb"]')].map(e => e.textContent),
    gaps: document.querySelector('[data-testid="gaps"]')?.textContent ?? null,
    empty: !!document.querySelector('[data-testid="ring-empty"]'),
    notTuned: !!document.querySelector('[data-testid="not-tuned"]'),
  }));
}

async function tune(page, stream) {
  await page.getByTestId(`tune-${STATION}-${stream}`).click();
  await page.waitForFunction(s => document.querySelector('[data-testid="tuned-channel"]')?.textContent === s,
    `${STATION}:${stream}`, {timeout: 10000});
  await page.waitForTimeout(1500);   // one or two ring polls
  emit("tuned", {stream, ring: await ring(page)});
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
  await page.getByTestId(`tune-${STATION}-hymn`).waitFor({timeout: 15000});
  emit("loaded", {stations: await page.locator('[data-testid="station"]').count()});

  if (phase === "early") {
    await tune(page, "hymn");
    await shot(page, "01-tuned-hymn.png");
    await page.waitForTimeout(15000);
    emit("watching", {stream: "hymn", ring: await ring(page)});
    await page.getByTestId("leave").click();
    await page.getByTestId("not-tuned").waitFor({timeout: 5000});
    emit("left", {ring: await ring(page)});
    await shot(page, "02-left.png");
    await tune(page, "lens.weather");
    await shot(page, "03-retuned-weather.png");
    await page.waitForTimeout(10000);
    emit("watching", {stream: "lens.weather", ring: await ring(page)});
    await tune(page, "hymn");
  } else if (phase === "late") {
    await tune(page, "hymn");
    await page.waitForTimeout(3000);
    emit("late-view", {stream: "hymn", ring: await ring(page)});
    await shot(page, "04-late-page.png");
  } else if (phase === "drain") {
    await tune(page, "hymn");
    await page.waitForTimeout(3000);
    emit("after-stop", {stream: "hymn", ring: await ring(page)});
    await shot(page, "05-after-stop.png");
    await tune(page, "lens.weather");
    emit("after-stop", {stream: "lens.weather", ring: await ring(page)});
  }
  emit("done", {console_errors: consoleErrors});
  await browser.close();
})().catch(e => { emit("error", {error: String(e)}); process.exit(1); });

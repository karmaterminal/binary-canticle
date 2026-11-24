// k6 controls the bounded closed-loop load; HTTP is control, never fake UDP.
import http from 'k6/http';
import { check, fail, sleep } from 'k6';
import exec from 'k6/execution';
import { Counter, Rate, Trend } from 'k6/metrics';

function bounded(name, low, high) {
  const value = Number(__ENV[name]);
  if (!Number.isInteger(value) || value < low || value > high) fail('invalid ' + name);
  return value;
}
const items = bounded('ITEMS', 1, 16);
const vus = bounded('VUS', 1, 2);
const pace = bounded('PACE_MS', 250, 1000);
const base = __ENV.FIXTURE_URL;
if (!/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(base || '') || !__ENV.FIXTURE_TOKEN)
  fail('only a loopback fixture with an ephemeral token is supported');
const params = { headers: { Authorization: 'Bearer ' + __ENV.FIXTURE_TOKEN,
                           'Content-Type': 'application/json' }, timeout: '4s', redirects: 0 };
const offered = new Counter('canticle_offered');
const delivered = new Counter('canticle_delivered');
const missed = new Rate('canticle_deadline_miss');
const censored = new Trend('canticle_offer_to_record_or_deadline_ms', true);
const arrivalCensored = new Trend('canticle_arrival_to_record_or_deadline_ms', true);
const arrivalSuccess = new Trend('canticle_arrival_to_record_success_ms', true);

export const options = {
  scenarios: { baseline: { executor: 'shared-iterations', vus, iterations: items,
                           maxDuration: '50s', gracefulStop: '1s' } },
  thresholds: {
    checks: ['rate==1'],
    canticle_offered: ['count==' + items],
    canticle_deadline_miss: ['rate==0'],
    canticle_delivered: ['count==' + items],
  },
  noConnectionReuse: true,
  summaryTrendStats: ['min', 'med', 'p(95)', 'max', 'count'],
};

export default function () {
  offered.add(1); // attempts count even if control HTTP or fixture fails
  const response = http.post(base + '/offer', JSON.stringify({id: exec.scenario.iterationInTest}), params);
  let row;
  try { row = response.json(); } catch (_) { row = {}; }
  const valid = check(response, {
    'fixture returned a settled offer': r => r.status === 200 && row.settled === true,
    'station accepted': () => row.accepted === true,
    'complete surface record by deadline': () => row.delivered === true,
  });
  missed.add(!valid);
  delivered.add(valid ? 1 : 0);
  if (response.status === 200 && Number.isFinite(row.offer_to_record_or_deadline_ms)) {
    censored.add(row.offer_to_record_or_deadline_ms);
    if (row.arrival_to_record_or_deadline_ms !== null)
      arrivalCensored.add(row.arrival_to_record_or_deadline_ms);
    if (row.arrival_to_record_ms !== null) arrivalSuccess.add(row.arrival_to_record_ms);
  }
  sleep(pace / 1000);
}

export function teardown() {
  const response = http.get(base + '/stats', params);
  let stats;
  try { stats = response.json(); } catch (_) { stats = {}; }
  check(response, {
    'all planned offers accounted': r => r.status === 200 && stats.counts.offered === items,
    'conservation holds': () => stats.accounting === true && stats.counts.pending === 0,
    'no duplicate surface records': () => stats.counts.duplicate_surface_records === 0,
    'no fixture errors': () => stats.errors.length === 0 && stats.production_tasks_alive === true,
  });
}

export function handleSummary(data) {
  return { [__ENV.SUMMARY_PATH]: JSON.stringify(data, null, 2) + '\n' };
}

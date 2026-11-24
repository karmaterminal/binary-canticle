"""Offline reference comparator: not a load generator or live-hearing proof.
Times are seconds on ONE monotonic clock; bounds are predeclared.
"""
import math

def judge(items, expected_ids, *, stage, flood_end_s, captured_until_s, budget_s):
    def time(x):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
            raise ValueError('invalid monotonic time')
        return x
    end, captured, budget = map(time, (flood_end_s, captured_until_s, budget_s))
    if budget <= 0 or (stage != 'at_daemon_s' and not stage.startswith('push:')):
        raise ValueError('declare one supported observation stage and a positive budget')
    expected = list(expected_ids)
    if not expected or len(set(expected)) != len(expected):
        raise ValueError('nonempty unique producer-side expected IDs required')
    by_id = {}
    for item in items:
        identity = item['idem']
        if identity in by_id:
            raise ValueError('duplicate producer-side item ID')
        by_id[identity] = item
    if set(by_id) != set(expected):
        raise ValueError('producer manifest and result IDs differ')
    out = dict(expected=len(expected), on_time=0, late=0, missing=0,
               catchup_after_flood=0, latencies_s=[])
    for identity in expected:
        item = by_id[identity]
        sent = time(item['sung_at_s'])
        if sent >= end or sent + budget > end or captured < sent + budget:
            raise ValueError('load/capture window does not cover the declared deadline')
        observed = (item.get('at_daemon_s') if stage == 'at_daemon_s'
                    else (item.get('pushed_at_s') or {}).get(stage.removeprefix('push:')))
        if observed is None:
            out['missing'] += 1
            continue
        observed = time(observed)
        if observed < sent or observed > captured:
            raise ValueError('observation lies outside its causal capture window')
        latency = observed - sent
        out['latencies_s'].append(latency)
        out['on_time' if latency <= budget else 'late'] += 1
        out['catchup_after_flood'] += observed >= end
    out['pass'] = out['on_time'] == out['expected']
    return out

"""🌫's paired regression (#173 issuecomment-7125278653): a known positive row, each field broken in turn, must be INVALID and not PASS,
and the stronger preflight must change no verdict of the rows that were measured. Usage: test_judge_rows.py [<newcomer_rows.py's json>...]"""

import copy
import json
import math
import sys
import unittest

from judge_rows import ITEMS, newcomer

FILES = [a for a in sys.argv[1:] if a.endswith(".json")]
ROW = {"row": "churn-40-20000-5", "run": 0, "cryptography": "50.0.1", "lowest_second": 20_000, "sung": ITEMS,
       "first_valid_frame_s": 0.04, "flood_end_after_last_item_sent_s": 61.1, "first_miss": False, "item_misses": 0,
       "items": [{"sent_s": round(0.15 * n, 4), "latency_s": 0.02} for n in range(ITEMS)]}


class Preflight(unittest.TestCase):
    def test_the_row_as_it_is_passes(self):
        got = newcomer(copy.deepcopy(ROW))
        self.assertTrue(got["first"]["pass"] and got["items"]["pass"])

    def test_a_broken_field_is_invalid(self):
        for field, bad in (("lowest_second", math.nan), ("lowest_second", math.inf), ("lowest_second", -math.inf), ("lowest_second", -1),
                           ("lowest_second", True), ("lowest_second", None), ("lowest_second", "20000"), ("lowest_second", 18_999),
                           ("sung", 0), ("sung", ITEMS - 1), ("sung", True), ("sung", None), ("items", ROW["items"][:-1]),
                           ("items", []), ("cryptography", "41.0.7")):
            with self.subTest(field=field, bad=bad):
                r = copy.deepcopy(ROW)
                r[field] = bad
                with self.assertRaises(ValueError):
                    newcomer(r)

    def test_a_late_and_a_missing_item_are_both_misses(self):
        r = copy.deepcopy(ROW)
        r["items"][3]["latency_s"], r["items"][4]["latency_s"] = 2.01, None
        got = newcomer(r)["items"]
        self.assertEqual((got["late"], got["missing"], got["on_time"], got["pass"]), (1, 1, ITEMS - 2, False))

    def test_no_measured_row_is_judged_otherwise_than_by_the_harness(self):
        for f in FILES:
            for r in json.load(open(f)):
                with self.subTest(file=f, row=r["row"], tree=r["tree"], run=r["run"]):
                    got = newcomer(r)
                    self.assertEqual(got["first"]["pass"] and got["items"]["pass"], not (r["first_miss"] or r["item_misses"]))


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])

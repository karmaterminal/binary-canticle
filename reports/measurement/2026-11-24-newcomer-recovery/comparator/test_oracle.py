import math, unittest
from oracle import judge
class OracleTest(unittest.TestCase):
    def setUp(self):
        self.items = [dict(idem='a',sung_at_s=0,at_daemon_s=0,pushed_at_s={'ear0':0.1,'ear1':0.2}),dict(idem='b',sung_at_s=1,at_daemon_s=1.1,pushed_at_s={'ear0':1.2,'ear1':1.3})]
    def runrow(self,items=None,expected=('a','b'),**kw):
        args=dict(stage='at_daemon_s',flood_end_s=10,captured_until_s=20,budget_s=2);args.update(kw)
        return judge(self.items if items is None else items,expected,**args)
    def test_positive_zero_timestamp(self): self.assertTrue(self.runrow()['pass'])
    def test_boundary_inclusive(self):
        self.items[0]['at_daemon_s']=2
        self.assertTrue(self.runrow()['pass'])
    def test_missing_cannot_hide_in_percentile(self):
        self.items[1]['at_daemon_s']=None
        r=self.runrow();self.assertFalse(r['pass']);self.assertEqual((r['on_time'],r['missing']),(1,1))
    def test_late_fails_even_if_delivered(self):
        self.items[1]['at_daemon_s']=3.001
        r=self.runrow();self.assertFalse(r['pass']);self.assertEqual(r['late'],1)
    def test_catchup_not_recovery(self):
        self.items[1]['at_daemon_s']=11
        r=self.runrow();self.assertFalse(r['pass']);self.assertEqual(r['catchup_after_flood'],1)
    def test_all_recipients_independent(self):
        del self.items[0]['pushed_at_s']['ear1']
        self.assertTrue(self.runrow(stage='push:ear0')['pass'])
        self.assertFalse(self.runrow(stage='push:ear1')['pass'])
    def test_null_push_map_is_missing(self):
        self.items[0]['pushed_at_s']=None
        self.assertEqual(self.runrow(stage='push:ear0')['missing'],1)
    def test_empty(self):
        with self.assertRaises(ValueError): self.runrow([],())
    def test_omitted_producer_item(self):
        with self.assertRaises(ValueError): self.runrow(self.items[:1])
    def test_duplicate_producer_identity(self):
        with self.assertRaises(ValueError): self.runrow(self.items+self.items[:1])
    def test_duplicate_manifest(self):
        with self.assertRaises(ValueError): self.runrow(expected=('a','a'))
    def test_clock_backwards(self):
        self.items[1]['at_daemon_s']=0.5
        with self.assertRaises(ValueError): self.runrow()
    def test_nonfinite_and_bool(self):
        for bad in (math.nan,math.inf,-1,True,'0'):
            with self.subTest(bad=bad):
                self.items[0]['at_daemon_s']=bad
                with self.assertRaises(ValueError): self.runrow()
    def test_unknown_stage(self):
        with self.assertRaises(ValueError): self.runrow(stage='heard')
    def test_short_capture(self):
        with self.assertRaises(ValueError): self.runrow(captured_until_s=2)
    def test_flood_stops_before_deadline(self):
        with self.assertRaises(ValueError): self.runrow(flood_end_s=2)
    def test_observation_beyond_capture(self):
        self.items[0]['at_daemon_s']=21
        with self.assertRaises(ValueError): self.runrow()
if __name__=='__main__': unittest.main()

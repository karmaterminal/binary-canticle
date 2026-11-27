import base64
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from canticle import dns_browse
from canticle.__main__ import main
from canticle.dns_browse import Answer, Browser
from canticle.manifest import Manifest, StationEntry

PUB = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
PUB2 = bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')  # RFC 8032 TEST 2
SERVICE = '_canticle._udp.example.org.'
INSTANCE = 'cael.' + SERVICE
RUNE = 'rune.' + SERVICE
# Out of zone, with a suffix as long as example.org's: slicing the service off it would leave "cael".
ELSEWHERE = 'cael._canticle._udp.evilnet.org.'


def k_hint(pub):
    return 'ed25519:' + base64.b64encode(pub).decode()


class FakeResolver:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def resolve(self, name, kind):
        self.calls.append((name, kind))
        return self.answers.get((name, kind), Answer((), 60))


class BrowseTests(unittest.TestCase):
    def setUp(self):
        self.grant = StationEntry('cael', PUB, frozenset(), streams=('hymn', 'private'),
                                  public_streams=('hymn',))
        self.manifest = Manifest([self.grant])
        self.now = 0
        self.answers = {
            (SERVICE, 'PTR'): Answer((INSTANCE, 'stranger.' + SERVICE, 'out._canticle._udp.other.org.'), 300),
            (INSTANCE, 'SRV'): Answer(((0, 0, 47113, 'relay.example.org.'),), 120),
            (INSTANCE, 'TXT'): Answer(((f'sid={self.grant.key_id.hex()}',
                                       'k=ed25519:' + base64.b64encode(PUB).decode(),
                                       'streams=hymn,private'),), 120),
        }

    def test_public_catalog_only_and_mismatch(self):
        resolver = FakeResolver(self.answers)
        result = Browser(resolver, self.manifest, 'example.org', lambda: self.now).browse()
        self.assertEqual(result['stations'][0]['public_streams'], ['hymn'])
        self.assertEqual(result['stations'][0]['mismatches'], ['streams'])
        self.assertEqual(result['stations'][0]['locators'][0]['port'], 47113)
        self.assertEqual(len(result['stations']), 1)
        self.assertEqual(len(resolver.calls), 3)
        self.assertNotIn('private', str(result))

    def test_missing_catalog_fails_closed(self):
        m = Manifest([StationEntry('cael', PUB, frozenset(), streams=('hymn',))])
        resolver = FakeResolver(self.answers)
        self.assertEqual(Browser(resolver, m, 'example.org').browse()['stations'], [])
        self.assertEqual(resolver.calls, [(SERVICE, 'PTR')])

    def test_key_mismatch_alert_does_not_change_grant(self):
        self.answers[(INSTANCE, 'TXT')] = Answer((('sid=0000000000000000', 'k=ed25519:bogus', 'streams=private'),), 120)
        row = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()['stations'][0]
        self.assertEqual(row['mismatches'], ['k', 'sid', 'streams'])
        self.assertEqual(row['public_streams'], ['hymn'])

    def test_duplicate_txt_keys_are_invalid_and_have_no_value(self):
        expected_sid = self.grant.key_id.hex()
        expected_key = 'ed25519:' + base64.b64encode(PUB).decode()
        self.answers[(INSTANCE, 'TXT')] = Answer((('sid=0000000000000000', 'k=ed25519:bogus',
                                                   'streams=hymn', f'SiD={expected_sid}'),
                                                  (f'K={expected_key}', 'SID=ffffffffffffffff')),
                                                 120)
        row = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()['stations'][0]
        self.assertEqual(row['mismatches'], ['txt-invalid'])
        self.assertEqual(row['key_id'], expected_sid)
        self.assertEqual(row['public_streams'], ['hymn'])

    def test_lone_mixed_case_txt_keys_are_checked_for_mismatch(self):
        self.answers[(INSTANCE, 'TXT')] = Answer((('SiD=0000000000000000',
                                                   'K=ed25519:bogus', 'StReAmS=private'),), 120)
        row = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()['stations'][0]
        self.assertEqual(row['mismatches'], ['k', 'sid', 'streams'])

    def test_oversized_txt_is_ignored_and_reported(self):
        self.answers[(INSTANCE, 'TXT')] = Answer(((('streams=' + 'x' * 5000),),), 120)
        row = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()['stations'][0]
        self.assertEqual(row['public_streams'], ['hymn'])
        self.assertEqual(row['mismatches'], ['txt-invalid'])

    def test_ttl_and_negative_cache(self):
        resolver = FakeResolver(self.answers)
        browser = Browser(resolver, self.manifest, 'example.org', lambda: self.now)
        browser.browse(); browser.browse()
        self.assertEqual(len(resolver.calls), 3)
        self.now = 121
        browser.browse()
        self.assertEqual(len(resolver.calls), 5)
        resolver = FakeResolver({})
        browser = Browser(resolver, self.manifest, 'example.org', lambda: self.now)
        browser.browse(); browser.browse()
        self.assertEqual(len(resolver.calls), 1)
        self.now += 60
        browser.browse()
        self.assertEqual(len(resolver.calls), 2)

    def test_bounded_and_out_of_zone(self):
        self.answers[(SERVICE, 'PTR')] = Answer(tuple(f'cael{i}.{SERVICE}' for i in range(40)), 300)
        result = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()
        self.assertTrue(result['truncated'])
        self.assertEqual(result['stations'], [])
        self.answers[(SERVICE, 'PTR')] = Answer((INSTANCE,), 300)
        self.answers[(INSTANCE, 'SRV')] = Answer(((0, 0, 1, 'evil.other.org.'),), 120)
        row = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()['stations'][0]
        self.assertEqual(row['locators'], [])
        self.assertIn('srv-target', row['mismatches'])

    def test_invalid_domain(self):
        with self.assertRaises(ValueError):
            Browser(FakeResolver({}), self.manifest, 'example.org/evil')


class FindTests(unittest.TestCase):
    """Predicate search over the browse: what a station sings, as its manifest grant says (§13.1)."""

    def setUp(self):
        self.cael = StationEntry('cael', PUB, frozenset(),
                                 streams=('ops.alarm', 'ops.night.watch', 'hymn', 'ops.private'),
                                 public_streams=('ops.alarm', 'ops.night.watch', 'hymn'))
        self.rune = StationEntry('rune', PUB2, frozenset(), streams=('hymn', 'opsx.y'),
                                 public_streams=('hymn', 'opsx.y'))
        self.manifest = Manifest([self.cael, self.rune])
        self.answers = {
            (SERVICE, 'PTR'): Answer((INSTANCE, RUNE), 300),
            (INSTANCE, 'SRV'): Answer(((0, 0, 47113, 'cael.example.org.'),), 120),
            (INSTANCE, 'TXT'): Answer((('txtvers=1', f'sid={self.cael.key_id.hex()}', 'k=' + k_hint(PUB),
                                        'streams=ops.alarm,ops.night.watch,hymn'),), 120),
            (RUNE, 'SRV'): Answer(((0, 0, 9999, 'rune.example.org.'),), 120),
            (RUNE, 'TXT'): Answer((('txtvers=1', f'sid={self.rune.key_id.hex()}', 'k=' + k_hint(PUB2),
                                    'streams=hymn,opsx.y'),), 120),
        }

    def find(self, *where, resolver=None):
        resolver = resolver or FakeResolver(self.answers)
        return dns_browse.find('example.org', list(where), manifest=self.manifest, query=resolver.resolve)

    @staticmethod
    def names(result):
        return [row['station'] for row in result['stations']]

    def test_stream_glob_matches_public_streams_only(self):
        result = self.find('streams=ops.*')
        self.assertEqual(self.names(result), ['cael'])
        self.assertEqual(result['stations'][0]['matched_on'],
                         [{'key': 'streams', 'pattern': 'ops.*', 'values': ['ops.alarm', 'ops.night.watch'],
                           'values_truncated': False}])
        self.assertEqual(result['where'], [{'key': 'streams', 'pattern': 'ops.*'}])
        self.assertEqual((result['refused'], result['truncated']), ([], False))
        self.assertNotIn('ops.private', json.dumps(result))

    def test_glob_wildcards(self):
        self.assertEqual(self.names(self.find('streams=*')), ['cael', 'rune'])
        self.assertEqual(self.names(self.find('streams=hymn')), ['cael', 'rune'])
        self.assertEqual(self.names(self.find('streams=*.y')), ['rune'])
        # "?" is one character, and a pattern without a wildcard is the whole name.
        hit = self.find('streams=ops.?????')['stations']
        self.assertEqual([(r['station'], r['matched_on'][0]['values']) for r in hit], [('cael', ['ops.alarm'])])
        self.assertEqual(self.find('streams=ops')['stations'], [])
        self.assertEqual(self.find('streams=ops.alar')['stations'], [])

    def test_hit_is_the_browse_row_plus_matched_on(self):
        rows = Browser(FakeResolver(self.answers), self.manifest, 'example.org').browse()['stations']
        hit = dict(self.find('streams=ops.*')['stations'][0])
        hit.pop('matched_on')
        self.assertEqual(hit, rows[0])

    def test_exact_sid_and_k(self):
        rune_sid = self.rune.key_id.hex()
        result = self.find(f'sid={rune_sid}')
        self.assertEqual(self.names(result), ['rune'])
        self.assertEqual(result['stations'][0]['matched_on'],
                         [{'key': 'sid', 'pattern': rune_sid, 'values': [rune_sid], 'values_truncated': False}])
        # DNS-SD keys are case-insensitive (RFC 6763 §6.4); a key id is hex, so its digits are too.
        self.assertEqual(self.names(self.find(f'SiD={rune_sid.upper()}')), ['rune'])
        self.assertEqual(self.names(self.find('k=' + k_hint(PUB))), ['cael'])
        self.assertEqual(self.names(self.find('K=' + k_hint(PUB))), ['cael'])
        # Other values are exact: base64 is case-sensitive.
        self.assertEqual(self.find('k=' + k_hint(PUB).swapcase().replace('ED25519:', 'ed25519:'))['stations'], [])

    def test_predicates_are_anded(self):
        rune_sid = self.rune.key_id.hex()
        result = self.find('streams=hymn', f'sid={rune_sid}')
        self.assertEqual(self.names(result), ['rune'])
        self.assertEqual([m['key'] for m in result['stations'][0]['matched_on']], ['streams', 'sid'])
        self.assertEqual(self.find('streams=ops.*', f'sid={rune_sid}')['stations'], [])
        # Each predicate is on the station: two stream predicates may match different streams.
        self.assertEqual(self.names(self.find('streams=ops.alarm', 'streams=hymn')), ['cael'])

    def test_no_match_is_an_empty_list_not_an_error(self):
        result = self.find('streams=nobody.*')
        self.assertEqual((result['stations'], result['refused'], result['truncated']), ([], [], False))

    def test_txt_never_adds_a_stream_or_a_key(self):
        bogus = '0000000000000000'
        self.answers[(RUNE, 'TXT')] = Answer((('txtvers=1', f'sid={bogus}', 'k=' + k_hint(PUB2),
                                               'streams=hymn,opsx.y,ops.secret'),), 120)
        self.assertEqual(self.names(self.find('streams=ops.*')), ['cael'])
        self.assertEqual(self.find(f'sid={bogus}')['stations'], [])
        # The grant's own key id still finds it; the disagreement is reported, as browse reports it.
        row = self.find(f'sid={self.rune.key_id.hex()}')['stations'][0]
        self.assertEqual(row['mismatches'], ['sid', 'streams'])

    def test_malformed_txt_is_refused(self):
        sid = self.cael.key_id.hex()
        for txt in ((('streams=ops.alarm', f'sid={sid}', f'SID={sid}'),),   # a repeated key
                    ((('streams=' + 'x' * 5000),),),                         # oversized
                    (('streams=ops.alarm', 'k=�'),)):                   # not UTF-8
            self.answers[(INSTANCE, 'TXT')] = Answer(txt, 120)
            result = self.find('streams=ops.*')
            self.assertEqual(result['stations'], [])
            self.assertEqual(result['refused'], [{'station': 'cael', 'key_id': sid, 'reason': 'txt-invalid'}])
            self.assertNotIn('47113', json.dumps(result))  # no locator from a refused record

    def test_only_matching_candidates_are_queried(self):
        self.answers[(RUNE, 'TXT')] = Answer(((('streams=' + 'x' * 5000),),), 120)
        resolver = FakeResolver(self.answers)
        result = self.find('streams=ops.*', resolver=resolver)
        self.assertEqual((self.names(result), result['refused']), (['cael'], []))
        self.assertEqual(resolver.calls, [(SERVICE, 'PTR'), (INSTANCE, 'SRV'), (INSTANCE, 'TXT')])

    def test_out_of_zone_instance_is_ignored_even_if_it_matches(self):
        self.answers[(SERVICE, 'PTR')] = Answer((ELSEWHERE,), 300)
        self.answers[(ELSEWHERE, 'SRV')] = self.answers[(INSTANCE, 'SRV')]
        self.answers[(ELSEWHERE, 'TXT')] = self.answers[(INSTANCE, 'TXT')]
        resolver = FakeResolver(self.answers)
        result = self.find('streams=ops.*', resolver=resolver)
        self.assertEqual((result['stations'], result['refused']), ([], []))
        self.assertEqual(resolver.calls, [(SERVICE, 'PTR')])

    def test_out_of_zone_srv_target_is_dropped(self):
        self.answers[(INSTANCE, 'SRV')] = Answer(((0, 0, 47113, 'cael.example.org.'),
                                                  (0, 0, 47113, 'relay.evilnet.org.')), 120)
        row = self.find('streams=ops.*')['stations'][0]
        self.assertEqual(row['locators'], [{'target': 'cael.example.org.', 'port': 47113, 'priority': 0, 'weight': 0}])
        self.assertIn('srv-target', row['mismatches'])
        self.assertNotIn('evilnet', json.dumps(row))

    def test_instance_cap_is_reported(self):
        filler = [f'x{i}.{SERVICE}' for i in range(40)]
        self.answers[(SERVICE, 'PTR')] = Answer(tuple(filler[:5] + [INSTANCE] + filler[5:]), 300)
        result = self.find('streams=ops.*')
        self.assertEqual((self.names(result), result['truncated']), (['cael'], True))
        # Past the cap, "no hit" says only that the first 32 instances had none.
        self.answers[(SERVICE, 'PTR')] = Answer(tuple(filler[:35] + [INSTANCE]), 300)
        result = self.find('streams=ops.*')
        self.assertEqual((result['stations'], result['truncated']), ([], True))

    def test_matching_sees_the_whole_public_catalog_and_bounds_what_it_prints(self):
        many = tuple(f's{i:02d}' for i in range(40)) + ('ops.late',)
        wide = StationEntry('cael', PUB, frozenset(), streams=many, public_streams=many)
        self.manifest = Manifest([wide, self.rune])
        row = self.find('streams=ops.*')['stations'][0]
        self.assertTrue(row['public_streams_truncated'])
        self.assertNotIn('ops.late', row['public_streams'])
        self.assertEqual(row['matched_on'][0]['values'], ['ops.late'])
        values = self.find('streams=s*')['stations'][0]['matched_on'][0]
        self.assertEqual((len(values['values']), values['values_truncated']), (dns_browse.MAX_PUBLIC_STREAMS, True))

    def test_invalid_predicates_are_refused_before_any_query(self):
        resolver = FakeResolver(self.answers)
        for bad in ('streams', '=ops.*', 'streams=', 'class=alarm', 'mode=lease', 'txtvers=1', 'station=cael',
                    'streams=OPS.*', 'streams=ops.[ab]', 'streams=ops alarm', 'streams=' + 'a' * 65,
                    'sid=xyz', 'sid=' + 'a' * 15, 'sid=*', 'k=ed25519:bogus', 'k=' + k_hint(PUB)[8:],
                    'k=ed25519:' + base64.b64encode(b'\x00' * 31).decode()):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.find(bad, resolver=resolver)
        with self.assertRaises(ValueError):
            self.find(resolver=resolver)
        with self.assertRaises(ValueError):
            self.find(*['streams=*'] * (dns_browse.MAX_WHERE + 1), resolver=resolver)
        with self.assertRaises(ValueError):
            dns_browse.find('example.org', 'streams=*', manifest=self.manifest, query=resolver.resolve)
        self.assertEqual(resolver.calls, [])

    def test_find_keeps_browse_domain_rules(self):
        for domain in ('example.org/evil', 'local', 'lan.local'):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                dns_browse.find(domain, ['streams=*'], manifest=self.manifest, query=FakeResolver({}).resolve)


class FindCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fleet = Path(tmp.name) / 'fleet.json'
        cael = StationEntry('cael', PUB, frozenset(), streams=('ops.alarm', 'hymn'), public_streams=('ops.alarm',))
        self.fleet.write_text(json.dumps(Manifest([cael]).to_json()))
        self.answers = {
            (SERVICE, 'PTR'): Answer((INSTANCE,), 300),
            (INSTANCE, 'SRV'): Answer(((0, 0, 47113, 'cael.example.org.'),), 120),
            (INSTANCE, 'TXT'): Answer((('txtvers=1', f'sid={cael.key_id.hex()}', 'streams=ops.alarm'),), 120),
        }

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(dns_browse, 'DnsPythonResolver', lambda: FakeResolver(self.answers)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['dns-find', '--domain', 'example.org', '--manifest', str(self.fleet), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_prints_hits_as_json(self):
        code, out, _ = self.run_cli('--where', 'streams=ops.*', '--where', 'STREAMS=*.alarm')
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual([r['station'] for r in result['stations']], ['cael'])
        self.assertEqual([m['pattern'] for m in result['stations'][0]['matched_on']], ['ops.*', '*.alarm'])

    def test_no_match_exits_zero(self):
        code, out, _ = self.run_cli('--where', 'streams=hymn')
        self.assertEqual((code, json.loads(out)['stations']), (0, []))

    def test_a_bad_predicate_exits_one(self):
        code, out, err = self.run_cli('--where', 'class=alarm')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('dns-find: ', err)

    def test_where_is_required(self):
        err = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(err):
            main(['dns-find', '--domain', 'example.org', '--manifest', str(self.fleet)])
        self.assertIn('required: --where', err.getvalue())


if __name__ == '__main__':
    unittest.main()

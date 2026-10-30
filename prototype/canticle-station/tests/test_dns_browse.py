import base64
import unittest

from canticle.dns_browse import Answer, Browser
from canticle.manifest import Manifest, StationEntry

PUB = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
SERVICE = '_canticle._udp.example.org.'
INSTANCE = 'cael.' + SERVICE


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


if __name__ == '__main__':
    unittest.main()

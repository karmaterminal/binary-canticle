import unittest
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle.dns_registration import Registration
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig
from canticle.wire import public_key_bytes


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.fail = False

    def publish(self, publication, lease):
        self.calls.append(('publish', publication, lease))
        if self.fail:
            raise RuntimeError('provider failure')
        return object()

    def renew(self, handle, publication, lease):
        self.calls.append(('renew', handle, publication, lease))
        if self.fail:
            raise RuntimeError('provider failure')

    def withdraw(self, handle):
        self.calls.append(('withdraw', handle))
        if self.fail:
            raise RuntimeError('provider failure')


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.grant = StationEntry('cael', public_key_bytes(self.key), frozenset(),
                                  streams=('hymn', 'private'), public_streams=('hymn',))
        self.manifest = Manifest([self.grant])
        self.station = Station(self.key, [StreamConfig('hymn', 'chatter'),
                                          StreamConfig('private', 'chatter')], epoch=1, grant=self.grant)
        self.provider = FakeProvider()
        self.now = 0

    def registration(self, **overrides):
        args = dict(enabled=True, zone='example.org', target='relay.example.org', port=47113,
                    clock=lambda: self.now)
        args.update(overrides)
        return Registration(self.station, self.manifest, self.provider, **args)

    def test_explicit_opt_in_and_public_only(self):
        with self.assertRaisesRegex(ValueError, 'opt-in'):
            self.registration(enabled=False)
        self.assertEqual(self.provider.calls, [])
        reg = self.registration()
        self.assertEqual(self.provider.calls, [])
        reg.publish()
        publication = self.provider.calls[0][1]
        self.assertEqual([(r.kind, r.ttl) for r in publication.records],
                         [('PTR', 300), ('SRV', 120), ('TXT', 120)])
        self.assertEqual(publication.records[0].value, 'cael._canticle._udp.example.org.')
        self.assertIn('streams=hymn', publication.records[2].value)
        self.assertNotIn('private', str(publication))
        self.assertEqual(self.provider.calls[0][2], 3600)

    def test_renew_and_withdraw_are_clock_bounded(self):
        reg = self.registration()
        reg.publish()
        with self.assertRaisesRegex(RuntimeError, 'already active'):
            reg.publish()
        self.now = 3599
        reg.renew()
        self.assertEqual(reg.expires_at, 7199)
        self.now = 7200
        with self.assertRaisesRegex(RuntimeError, 'no live lease'):
            reg.renew()
        reg.withdraw()
        self.assertEqual([c[0] for c in self.provider.calls], ['publish', 'renew'])
        reg.publish()
        reg.withdraw()
        self.assertEqual([c[0] for c in self.provider.calls], ['publish', 'renew', 'publish', 'withdraw'])

    def test_provider_failures_do_not_advance_state(self):
        reg = self.registration()
        self.provider.fail = True
        with self.assertRaises(RuntimeError):
            reg.publish()
        self.assertIsNone(reg.expires_at)
        self.provider.fail = False
        reg.publish()
        self.now = 10
        self.provider.fail = True
        with self.assertRaises(RuntimeError):
            reg.renew()
        self.assertEqual(reg.expires_at, 3600)
        with self.assertRaises(RuntimeError):
            reg.withdraw()
        self.assertEqual(reg.expires_at, 3600)

    def test_revocation_before_renew_refuses_update(self):
        reg = self.registration()
        reg.publish()
        self.manifest._by_kid[self.grant.key_id] = replace(self.grant, revoked=True)
        with self.assertRaisesRegex(RuntimeError, 'grant changed'):
            reg.renew()
        self.assertEqual([c[0] for c in self.provider.calls], ['publish'])

    def test_unsafe_inputs_refuse_before_provider(self):
        for kw in ({'zone': 'local'}, {'target': 'evil.org'}, {'lease_seconds': 7201},
                   {'lease_seconds': 0}, {'port': 0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.registration(**kw)
        self.assertEqual(self.provider.calls, [])
        empty = StationEntry('cael', public_key_bytes(self.key), frozenset(), streams=('hymn',))
        with self.assertRaisesRegex(ValueError, 'manifest'):
            Registration(self.station, Manifest([empty]), self.provider, enabled=True,
                         zone='example.org', target='relay.example.org', port=47113)
        self.manifest.add(StationEntry('cael', public_key_bytes(Ed25519PrivateKey.generate()), frozenset()))
        with self.assertRaisesRegex(ValueError, 'one active'):
            self.registration()


if __name__ == '__main__':
    unittest.main()

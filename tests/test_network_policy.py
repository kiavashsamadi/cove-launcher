"""Synthetic offline fixtures only: no DNS requests, subprocesses or TV access."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_network_policy as policy


def catalog(groups=None):
    return json.dumps(dict(schema=1, groups=groups or {
        "acr": ["measurement.example", "Sub.Measurement.example"],
        "advertising": ["ad.example"], "reporting": ["report.example"]})).encode()


class NetworkPreparation(unittest.TestCase):
    def test_explicit_groups_and_no_network_defaults(self):
        config, report = policy.prepare(catalog(), ["acr", "advertising"])
        self.assertEqual(report["domains"], ["ad.example", "measurement.example", "sub.measurement.example"])
        self.assertNotIn("report.example", config)
        self.assertIn("server=127.0.0.1#9053", config)
        self.assertIn("no-resolv\nno-hosts", config)
        self.assertNotIn("log-queries", config)
        self.assertFalse(report["qualified_for_deployment"])
        self.assertFalse(report["tv_contacted"])
        self.assertFalse(report["resolver_started"])

    def test_all_query_types_get_local_rule(self):
        config, report = policy.prepare(catalog(), ["acr"])
        for name in report["domains"]:
            self.assertIn("address=/" + name + "/\nlocal=/" + name + "/\n", config)

    def test_no_silent_empty_unknown_or_duplicate_selection(self):
        for selected in ([], ["unknown"], ["acr", "acr"], ["update_offers"]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                policy.prepare(catalog(), selected)

    def test_configuration_injection_and_ambiguous_names_rejected(self):
        bad = ["", " ", "ad.example\nserver=bad.example", "ad.example/path", "*.example",
               "https://ad.example", "ad.example:53", "127.0.0.1", "::1", "ad.example.",
               "ad..example", "-ad.example", "ad_.example", "ad.example ", "é.example",
               "com", "a" * 64 + ".example", "ad\x00.example", "a." * 130 + "example"]
        for name in bad:
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.prepare(catalog({"acr": [name]}), ["acr"])

    def test_shared_service_parents_rejected_but_specific_hosts_allowed(self):
        for name in policy.SHARED_HOSTS | {"com", "net", "tv"}:
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.prepare(catalog({"acr": [name]}), ["acr"])
        self.assertEqual(policy.domain("acr.samsungcloud.tv"), "acr.samsungcloud.tv")

    def test_schema_and_duplicate_json_keys_fail(self):
        bad = [b'{}', b'[]', b'{"schema":1,"schema":1,"groups":{}}',
               b'{"schema":1,"groups":{"acr":["a.example"],"acr":["b.example"]}}',
               b'\xef\xbb\xbf' + catalog(), b'\xff', catalog() + b' extra',
               json.dumps(dict(schema=True, groups={"acr": ["a.example"]})).encode(),
               json.dumps(dict(schema=1, groups={}, extra=True)).encode(),
               json.dumps(dict(schema=1, groups={"acr": []})).encode(),
               json.dumps(dict(schema=1, groups={"acr": "a.example"})).encode(),
               json.dumps(dict(schema=1, groups={"unknown": ["a.example"]})).encode()]
        for data in bad:
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                policy.prepare(data, ["acr"])

    def test_bounds_and_non_string_domains(self):
        for data in (b" " * (policy.MAX_BYTES + 1), catalog({"acr": [None]}),
                     catalog({"acr": ["a.example"] * (policy.MAX_DOMAINS + 1)})):
            with self.assertRaises(ValueError):
                policy.prepare(data, ["acr"])

    def test_normalized_deduplication_and_determinism(self):
        data = catalog({"acr": ["A.example", "a.example"], "advertising": ["a.example"]})
        first = policy.prepare(data, ["acr", "advertising"])
        self.assertEqual(first, policy.prepare(data, ["advertising", "acr"]))
        self.assertEqual(first[1]["domains"], ["a.example"])

    def test_failed_candidates_never_replace_previous_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / "catalog.json"; output = root / "reviews" / "first"
            source.write_bytes(catalog())
            policy.write_review(source, ["acr"], output, root / "reviews")
            original = {p.name: p.read_bytes() for p in output.iterdir()}
            source.write_bytes(b"not JSON")
            with self.assertRaises(ValueError):
                policy.write_review(source, ["acr"], root / "reviews" / "bad", root / "reviews")
            self.assertFalse((root / "reviews" / "bad").exists())
            source.write_bytes(catalog())
            with self.assertRaises(ValueError):
                policy.write_review(source, ["advertising"], output, root / "reviews")
            self.assertEqual(original, {p.name: p.read_bytes() for p in output.iterdir()})
            self.assertEqual(set(original), {"manifest.json", "dnsmasq-lab.conf", "review.json"})

    def test_output_cannot_escape_private_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / "catalog.json"; source.write_bytes(catalog())
            for output in (root / "public", root / "private", root / "private" / ".." / "public"):
                with self.assertRaises(ValueError):
                    policy.write_review(source, ["acr"], output, root / "private")

    def test_symlink_output_alias_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / "catalog.json"; source.write_bytes(catalog())
            private = root / "private"; private.mkdir(); real = private / "real"; real.mkdir()
            alias = private / "alias"
            try:
                os.symlink(real, alias, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Host does not allow symlink creation")
            with self.assertRaises(ValueError):
                policy.write_review(source, ["acr"], alias / "review", private)


if __name__ == "__main__":
    unittest.main()

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from simulate_dns_recovery import Conflict, MemoryBackend, Plan, activate, exercise, prepare, recover


class RecoveryModelTests(unittest.TestCase):
    def ready(self):
        b, p = MemoryBackend(), Plan()
        prepare(b, p)
        activate(b, p)
        return b, p

    def test_every_activation_and_recovery_interruption(self):
        result = exercise()
        self.assertEqual(result["modeled_interruptions_recovered"], 10)
        self.assertFalse(result["production_dns_qualified"])
        self.assertFalse(result["native_transaction_qualified"])

    def test_inverse_order_and_repeat(self):
        b, p = self.ready()
        recover(b, p)
        self.assertEqual(b.events[-5:], ["rule-removed:v6", "rule-removed:v4",
                                       "dns-restored", "resolver-stopped", "recovery-verified"])
        recover(b, p)
        self.assertFalse(b.resolver)
        self.assertEqual(b.rules, {"vendor": "vendor-rule"})

    def test_dns_conflict_retains_resolver_and_foreign_change(self):
        b, p = self.ready()
        b.dns = "independent-change"
        before = copy.deepcopy(b)
        with self.assertRaises(Conflict):
            recover(b, p)
        self.assertEqual(b, before)

    def test_owned_rule_conflict_causes_no_partial_inverse(self):
        for key in Plan().rules:
            b, p = self.ready()
            b.rules[key] = "independent-change"
            before = copy.deepcopy(b)
            with self.subTest(key=key), self.assertRaises(Conflict):
                recover(b, p)
            self.assertEqual(b, before)

    def test_unrelated_rule_change_preserved(self):
        b, p = self.ready()
        b.rules["vendor"] = "new-vendor-rule"
        b.rules["other-owner"] = "other-rule"
        recover(b, p)
        self.assertEqual(b.rules, {"vendor": "new-vendor-rule", "other-owner": "other-rule"})

    def test_partial_or_foreign_journal_rejected(self):
        for patch in (None, {}, {"token": "other"}):
            b, p = self.ready()
            b.snapshot = patch
            before = copy.deepcopy(b)
            with self.subTest(patch=patch), self.assertRaises(Conflict):
                recover(b, p)
            self.assertEqual(b, before)

    def test_changed_plan_rejected(self):
        b, _ = self.ready()
        with self.assertRaises(Conflict):
            recover(b, Plan(rule6="different-rule"))
        self.assertTrue(b.resolver)

    def test_preexisting_candidate_not_adopted(self):
        for b in (MemoryBackend(dns="candidate-loopback"),
                  MemoryBackend(rules={"synthetic-trial:v4": "unowned"}),
                  MemoryBackend(resolver=True)):
            with self.subTest(b=b), self.assertRaises(Conflict):
                prepare(b, Plan())
            self.assertIsNone(b.snapshot)

    def test_activation_drift_rejected(self):
        b, p = MemoryBackend(), Plan()
        prepare(b, p)
        b.dns = "external-change"
        with self.assertRaises(Conflict):
            activate(b, p)
        self.assertFalse(b.resolver)

    def test_dead_worker_recovery_still_restores_route(self):
        b, p = self.ready()
        b.resolver = False
        recover(b, p)
        self.assertEqual(b.dns, "original-dns")
        self.assertEqual(b.rules, {"vendor": "vendor-rule"})

    def test_change_between_inverse_steps_is_not_overwritten(self):
        b, p = self.ready()
        original_event = b.event
        def event(name):
            original_event(name)
            if name == "rule-removed:v6":
                b.rules[p.token + ":v4"] = "concurrent-replacement"
        b.event = event
        with self.assertRaises(Conflict):
            recover(b, p)
        self.assertTrue(b.resolver)
        self.assertEqual(b.rules[p.token + ":v4"], "concurrent-replacement")

    def test_change_before_worker_stop_retains_worker(self):
        for replacement in ("dns", "rule"):
            b, p = self.ready()
            original_event = b.event
            def event(name):
                original_event(name)
                if name == "dns-restored":
                    if replacement == "dns":
                        b.dns = "independent-change"
                    else:
                        b.rules[p.token + ":v6"] = "independent-rule"
            b.event = event
            with self.subTest(replacement=replacement), self.assertRaises(Conflict):
                recover(b, p)
            self.assertTrue(b.resolver)

    def test_activation_change_between_steps_refused(self):
        b, p = MemoryBackend(), Plan()
        prepare(b, p)
        original_event = b.event
        def event(name):
            original_event(name)
            if name == "resolver-ready":
                b.dns = "concurrent-setting"
        b.event = event
        with self.assertRaises(Conflict):
            activate(b, p)
        self.assertEqual(b.dns, "concurrent-setting")
        self.assertEqual(b.rules, {"vendor": "vendor-rule"})


if __name__ == "__main__":
    unittest.main()

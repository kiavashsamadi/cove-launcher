import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_native_retry as checker
from test_dns_controller_loss import controller


def fixture():
    value = controller(flow=True)
    r = value["preflight_report"]
    r["scope"] = "isolated-dns-libc-retry-v1"
    r.update(native_libc_exercised=True, native_active_response_passed=True, native_context_closed=True,
             native_primary_first_call_passed=True, native_primary_second_call_passed=True,
             native_backup_first_call_passed=True, native_backup_second_call_passed=True,
             native_test_process_unprivileged=False)
    phases = ("baseline-first", "baseline-repeat", "filtered-first", "filtered-repeat",
              "primary-first", "primary-second", "backup-first", "backup-second")
    r["native_checks"] = [dict(phase=p, success=True, errno=0,
        bytes=32 if p.startswith("filtered") else 48, elapsed_ms=2,
        socket_identity="socket:[" + str(101 if i < 2 else 102 if i < 4 else 103) + "]")
        for i, p in enumerate(phases)]
    return value


class NativeRetryTests(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(ValueError):
            checker.assess(value)

    def test_narrow_success_without_raw_identity_output(self):
        result = checker.assess(fixture())
        self.assertEqual(result["native_queries_passed"], 8)
        self.assertTrue(result["native_first_call_reconnected"])
        for key in ("all_native_clients_qualified", "live_network_recovery_qualified", "production_dns_qualified"):
            self.assertIs(result[key], False)
        self.assertNotIn("socket:", json.dumps(result))

    def test_requires_reconnect_and_reuse(self):
        for index, identity in ((1, "socket:[999]"), (4, "socket:[102]"), (7, "socket:[999]"), (2, None)):
            value = fixture(); value["preflight_report"]["native_checks"][index]["socket_identity"] = identity
            self.reject(value)

    def test_requires_every_query_in_order(self):
        value = fixture(); value["preflight_report"]["native_checks"].pop(); self.reject(value)
        value = fixture(); value["preflight_report"]["native_checks"].reverse(); self.reject(value)

    def test_rejects_native_errors_and_weak_types(self):
        for key, bad in (("success", False), ("success", 1), ("errno", True), ("errno", 104),
                         ("bytes", 0), ("elapsed_ms", True), ("elapsed_ms", 1401)):
            value = fixture(); value["preflight_report"]["native_checks"][4][key] = bad; self.reject(value)

    def test_rejects_unproven_privilege_claim_or_missing_flags(self):
        for key, bad in (("native_test_process_unprivileged", True), ("native_context_closed", False),
                         ("native_primary_first_call_passed", False), ("native_backup_second_call_passed", None)):
            value = fixture(); value["preflight_report"][key] = bad; self.reject(value)

    def test_retains_full_recovery_and_cleanup_requirements(self):
        for key in ("host_dns_and_firewall_unchanged", "rule_controller_killed", "automatic_artifact_cleanup_passed"):
            value = fixture(); value["preflight_report"][key] = False; self.reject(value)
        value = fixture(); value["cleanup"]["sdk_helpers_and_gates_absent"] = False; self.reject(value)


if __name__ == "__main__":
    unittest.main()

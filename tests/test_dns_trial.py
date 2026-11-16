"""Synthetic outcomes only; no private TV receipts or executable payloads."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_trial as trial


def common(scope, children, completed=True):
    fingerprints = {k: "a" * 64 for k in ("resolv_sha256", "resolv_target", "ipv4_rules", "ipv6_rules")}
    return dict(scope=scope, uid=0, euid=0, completed=completed,
                settings_written=False, firewall_changed=False, external_dns_sent=False,
                installed=False, resolver_file_and_firewall_unchanged=True,
                known_children_ended=True, network_fingerprints_before=fingerprints,
                network_fingerprints_after=fingerprints.copy(),
                started_children=list(range(100, 100 + children)), elapsed_ms=3000)


def functional():
    report = common("isolated-dns-runtime-trial-v3", 7)
    report.update({k: True for k in trial.FLAGS})
    report.update(query_count=233, upstream_queries=39)
    report["checks"] = [
        dict(zip(("name", "type", "ipv6", "tcp", "blocked", "passed"), (*check, True)))
        for check in trial.expected_checks()
    ]
    return report


def recovery(passed=False):
    report = common("isolated-dns-parent-recovery-v1", 8 if passed else 6, passed)
    if not passed:
        report.update(phase="parent-exit", cases=[], error=
                      "InvalidDataException: parent-death recovery failed; exact child fallback used")
    else:
        report["cases"] = [
            dict(mode=mode, parent_exit_code=code, worker_deadline_ms=6000,
                 ready_before_parent_exit=True, worker_identity_verified=True,
                 child_exited_without_direct_signal=True, ports_released=True, elapsed_ms=400)
            for mode, code in (("exit", 0), ("kill", 137))
        ]
    return report


def copy_attempt():
    report = common("isolated-dns-runtime-trial-v5", 5, False)
    report.update({k: True for k in trial.COPY_FLAGS})
    report.update(original_file_capabilities_before_sha256="a" * 64,
                  original_file_capabilities_after_sha256="a" * 64,
                  phase="responses", checks=[], query_count=0,
                  error="IOException: dns worker exited 85 ")
    return report


def outer(report, copied=False):
    passed = report["completed"]
    return dict(
        status="success" if passed else "stopped", root_proven=True,
        preflight_verified=passed, retained_flat_paths=[],
        errors=[] if passed else [dict(phase="diagnostic", type="RuntimeError",
            message="Fixed isolated DNS trial failed; bounded report retained")],
        cleanup={k: True for k in trial.CLEANUP | ({"temporary_dns_copy_removed"} if copied else set())},
        preflight_transport_result=dict(exit_code=0 if passed else 3, timed_out=False, stderr=""),
        preflight_report=report,
    )


class DnsReceiptTests(unittest.TestCase):
    def test_recovered_failure_never_becomes_a_pass(self):
        result = trial.verify(outer(functional()), outer(recovery()), outer(copy_attempt(), True))
        self.assertTrue(result["receipts_consistent"])
        self.assertEqual(result["isolated_response_checks_passed"], 233)
        self.assertFalse(result["automatic_parent_loss_recovery_passed"])
        self.assertTrue(result["fallback_cleanup_required"])
        self.assertEqual(result["temporary_copy_execution"], "refused_and_removed")
        self.assertFalse(result["production_dns_qualified"])
        self.assertFalse(result["all_tracking_blocked"])

    def test_synthetic_success_still_does_not_qualify_deployment(self):
        result = trial.verify(outer(functional()), outer(recovery(True)))
        self.assertTrue(result["automatic_parent_loss_recovery_passed"])
        self.assertFalse(result["fallback_cleanup_required"])
        self.assertFalse(result["production_dns_qualified"])
        self.assertEqual(result["temporary_copy_execution"], "not_assessed")

    def test_each_functional_recovery_proof_required(self):
        for key in trial.FLAGS:
            report = functional()
            report[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.functional_report(report)

    def test_complete_unique_query_coverage_required(self):
        for action in ("remove", "duplicate", "type", "ipv6"):
            report = functional()
            if action == "remove":
                report["checks"].pop()
            elif action == "duplicate":
                report["checks"][1] = copy.deepcopy(report["checks"][0])
            else:
                report["checks"][0][action] = 1.0
            with self.subTest(action=action), self.assertRaises(ValueError):
                trial.functional_report(report)

    def test_network_mutations_and_drift_rejected(self):
        for key in ("settings_written", "firewall_changed", "external_dns_sent", "installed"):
            report = functional()
            report[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.functional_report(report)
        for key in functional()["network_fingerprints_after"]:
            report = functional()
            report["network_fingerprints_after"][key] = "b" * 64
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.functional_report(report)

    def test_process_and_counter_types_are_strict(self):
        for key, value in (("started_children", [100] * 7), ("started_children", [[100]] * 7),
                           ("query_count", 233.0), ("uid", False), ("upstream_queries", 0),
                           ("elapsed_ms", 22000), ("scope", "deployment")):
            report = functional()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.functional_report(report)

    def test_parent_failure_requires_exact_known_outcome(self):
        for key, value in (("error", "unrelated failure"), ("cases", [{}]),
                           ("phase", "starting"), ("started_children", [100])):
            report = recovery()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.recovery_report(report)

    def test_parent_success_cannot_use_direct_kill_or_deadline(self):
        for key, value in (("child_exited_without_direct_signal", False), ("elapsed_ms", 6000),
                           ("parent_exit_code", 0), ("worker_deadline_ms", 500)):
            report = recovery(True)
            report["cases"][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.recovery_report(report)

    def test_both_parent_faults_required(self):
        report = recovery(True)
        report["cases"].pop()
        with self.assertRaises(ValueError):
            trial.recovery_report(report)

    def test_copy_cleanup_and_original_attributes_required(self):
        for key in trial.COPY_FLAGS:
            report = copy_attempt()
            report[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.copy_attempt_report(report)
        report = copy_attempt()
        report["original_file_capabilities_after_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            trial.copy_attempt_report(report)

    def test_copy_failure_cannot_claim_responses_passed(self):
        report = copy_attempt()
        report["query_count"] = 233
        with self.assertRaises(ValueError):
            trial.copy_attempt_report(report)

    def test_outer_cleanup_failure_is_not_recovered(self):
        for key in trial.CLEANUP:
            receipt = outer(recovery())
            receipt["cleanup"][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.verify(outer(functional()), receipt)
        receipt = outer(copy_attempt(), True)
        receipt["cleanup"]["temporary_dns_copy_removed"] = False
        with self.assertRaises(ValueError):
            trial.verify(outer(functional()), outer(recovery()), receipt)

    def test_transport_or_journal_error_cannot_be_hidden(self):
        receipt = outer(recovery())
        receipt["errors"].append(dict(phase="journal", message="failed"))
        with self.assertRaises(ValueError):
            trial.verify(outer(functional()), receipt)
        receipt = outer(recovery())
        receipt["preflight_transport_result"]["timed_out"] = True
        with self.assertRaises(ValueError):
            trial.verify(outer(functional()), receipt)

    def test_stopped_result_cannot_be_relabelled_success(self):
        receipt = outer(recovery())
        receipt.update(status="success", errors=[], preflight_verified=True)
        receipt["preflight_transport_result"]["exit_code"] = 0
        with self.assertRaises(ValueError):
            trial.verify(outer(functional()), receipt)

    def test_json_duplicate_keys_type_and_size_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "receipt.json"
            for content in ('{"a":1,"a":2}', "[]", " " * 1048577):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    trial.read_receipt(path)

    def test_cli_omits_private_input_on_failure(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            path.write_text('{"PRIVATE_SENTINEL":true}', encoding="utf-8")
            with patch.object(sys, "argv", ["checker", "--functional", str(path),
                                           "--recovery", str(path)]), redirect_stdout(output):
                self.assertEqual(trial.main(), 1)
        self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())
        self.assertNotIn(folder, output.getvalue())
        self.assertFalse(json.loads(output.getvalue())["receipts_consistent"])

    def test_cli_success_means_valid_evidence_not_recovery_success(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.json", Path(folder) / "b.json"
            a.write_text(json.dumps(outer(functional())), encoding="utf-8")
            b.write_text(json.dumps(outer(recovery())), encoding="utf-8")
            with patch.object(sys, "argv", ["checker", "--functional", str(a),
                                           "--recovery", str(b)]), redirect_stdout(output):
                self.assertEqual(trial.main(), 0)
        self.assertFalse(json.loads(output.getvalue())["automatic_parent_loss_recovery_passed"])


if __name__ == "__main__":
    unittest.main()

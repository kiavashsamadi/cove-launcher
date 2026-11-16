"""Synthetic records only: live-network evidence must remain distinct from isolation."""
import json
import unittest
from test_dns_owned_loss import fixture as isolated_fixture
import verify_dns_session_loss as checker


def fixture():
    args = isolated_fixture()
    r, after = args[0]["preflight_report"], args[1]["preflight_report"]
    r.update(scope="owned-host-dns-v2", host_firewall_changed=True, external_dns_sent=True,
             namespace_isolated=False, host_network_unchanged_before_loss=False,
             isolated_guard_refused_host=True, existing_rules_preserved_during_activation=True,
             ordinary_clients_redirected=False, host_activation_attempted=True,
             host_boot_identity="12345678-abcd-4321-abcd-123456789abc", renderer_sha256="a" * 64)
    after["renderer_sha256"] = "a" * 64
    r.pop("wrong_namespace_refused", None)
    return args


class OwnedHostTests(unittest.TestCase):
    def reject(self, args):
        with self.assertRaises(ValueError):
            checker.assess(*args, owned_host=True)

    def test_explicit_scope_and_limits(self):
        result = checker.assess(*fixture(), owned_host=True)
        self.assertTrue(result["owned_client_live_network_recovery_qualified"])
        for key in ("ordinary_tv_apps_qualified", "production_dns_qualified", "physical_pc_disconnect_tested"):
            self.assertFalse(result[key])
        for private in ("12345678", "0123456789abcdef", "net:["):
            self.assertNotIn(private, json.dumps(result))

    def test_scope_cannot_be_relabelled(self):
        self.reject(isolated_fixture())
        with self.assertRaises(ValueError):
            checker.assess(*fixture(), owned_clients=True)
        with self.assertRaises(ValueError):
            checker.assess(*fixture(), owned_clients=True, owned_host=True)

    def test_required_native_boundaries(self):
        for key in ("host_firewall_changed", "external_dns_sent", "host_activation_attempted",
                    "isolated_guard_refused_host", "existing_rules_preserved_during_activation",
                    "independent_helpers_armed_before_loss", "nonmember_unaffected"):
            args = fixture(); args[0]["preflight_report"][key] = False; self.reject(args)
        for key in ("ordinary_clients_redirected", "namespace_isolated", "host_network_unchanged_before_loss"):
            args = fixture(); args[0]["preflight_report"][key] = True; self.reject(args)

    def test_boot_and_installed_renderer(self):
        args = fixture(); args[0]["preflight_report"]["host_boot_identity"] = ""; self.reject(args)
        args = fixture(); args[1]["preflight_report"]["renderer_sha256"] = "b" * 64; self.reject(args)

    def test_separate_host_read_must_match(self):
        args = fixture(); args[1]["preflight_report"]["network_fingerprints_after"]["ipv4_rules"] = "b" * 64; self.reject(args)
        args = fixture(); args[1]["preflight_report"]["host_firewall_changed"] = True; self.reject(args)

    def test_fault_and_cleanup_cannot_be_omitted(self):
        args = fixture(); args[0]["independent_receipts"]["backup"] = ""; self.reject(args)
        args = fixture(); args[0]["cleanup"]["transient_units_absent"] = False; self.reject(args)
        args = fixture(); args[0]["preflight_report"]["backup_recovery_properties"]["CapabilityBoundingSet"] += " cap_sys_ptrace"; self.reject(args)

    def test_native_quotes_preserve_rule_value(self):
        args = fixture(); r = args[0]["preflight_report"]
        old = r["private_baseline6"]
        r["private_baseline6"] += "\n-N LOGGING\n-A LOGGING -j LOG --log-prefix DNS-Dropped:"
        for key in ("rescue", "backup"):
            marker = "partial_table6_begin\n" if key == "rescue" else "table6_begin\n"
            args[0]["independent_receipts"][key] = args[0]["independent_receipts"][key].replace(
                marker + old, marker + r["private_baseline6"].replace("DNS-Dropped:", '"DNS-Dropped:"'))
        checker.assess(*args, owned_host=True)
        args[0]["independent_receipts"]["backup"] = args[0]["independent_receipts"]["backup"].replace("DNS-Dropped:", "Changed:")
        self.reject(args)


def reconciled_fixture():
    args = fixture(); loss = args[0]
    loss.update(status="stopped", preflight_verified=False, errors=[{
        "phase": "payload_cleanup", "type": "ValueError", "message": "backup completion or tables"}])
    for key in ("payload_markers", "known_processes_ended", "owned_stage_removed"):
        loss["cleanup"].pop(key)
    rec = dict(status="clean", errors=[], root_launched=False, settings_changed=False, source_sha256="c" * 64)
    rec["cleanup"] = {k: True for k in ("all_known_processes_absent", "expected_signal_and_private_mount_cleanup_proved",
        "owned_units_slice_runtime_absent", "global_identity_preserved", "owned_stage_removed",
        "owned_archives_removed", "new_helpers_gates_absent")}
    rec["native_assessment"] = {k: True for k in ("complete_root_agent_loss_observed", "primary_partial_failure_observed",
        "backup_completed_both_tables", "witness_groups_empty", "witness_active_capabilities_empty")}
    rec["native_assessment"]["independent_dns_assertions"] = 24
    return args, rec


class ReconciledHostTests(unittest.TestCase):
    def assess(self, args, rec, digest="c" * 64):
        return checker.assess_reconciled_host(args[0], args[1], rec, args[2], args[3], digest)

    def test_original_remains_stopped_and_unchanged(self):
        args, rec = reconciled_fixture(); original = json.dumps(args)
        result = self.assess(args, rec)
        self.assertEqual(result["original_session_status"], "stopped")
        self.assertTrue(result["parser_rejection_reconciled"])
        self.assertFalse(result["original_receipt_rewritten"])
        self.assertEqual(original, json.dumps(args))

    def test_provenance_cleanup_and_failure_are_exact(self):
        for key in reconciled_fixture()[1]["cleanup"]:
            args, rec = reconciled_fixture(); rec["cleanup"][key] = False
            with self.assertRaises(ValueError): self.assess(args, rec)
        args, rec = reconciled_fixture()
        with self.assertRaises(ValueError): self.assess(args, rec, "d" * 64)
        args[0]["errors"][0]["message"] = "network changed"
        with self.assertRaises(ValueError): self.assess(args, rec)

    def test_reconciliation_cannot_hide_native_failure(self):
        args, rec = reconciled_fixture(); args[0]["independent_receipts"]["witness"] = ""
        with self.assertRaises(ValueError): self.assess(args, rec)


if __name__ == "__main__":
    unittest.main()

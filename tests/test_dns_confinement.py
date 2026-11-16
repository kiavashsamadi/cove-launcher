import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_confinement as checker
from test_dns_manager import fixture as prior_fixture


def permissions(batch):
    value = prior_fixture(batch); r = value["preflight_report"]
    r["scope"] = "isolated-dns-restricted-v" + str(batch)
    r["supplementary_groups_minimized"] = True
    if batch == 2:
        r["cases"] = r["cases"][2:]
        r["dns_checks"] = r["dns_checks"][2:]
    for c in r["cases"]:
        refused = c["case"] == "refused"
        c.pop("capabilities_empty")
        c.update(active_capabilities_empty=not refused, filesystem_restrictions_verified=not refused,
                 capability_bounding_set=None if refused else "00000000000000c0",
                 supplementary_groups=[], supplementary_groups_minimized=not refused)
        if not refused:
            c["properties"].update(checker.RESTRICTED)
    r["owned_units"] = [c["unit"] for c in r["cases"]]
    r["unit_pids"] = [c["worker_pid"] for c in r["cases"] if c["case"] != "refused"]
    return value


def routing():
    value = permissions(1); r = value["preflight_report"]
    r["scope"] = "isolated-dns-routing-v8"
    for key in checker.ROUTE_FLAGS + checker.SUPERVISED_FLAGS:
        r[key] = True
    for key in ("host_firewall_changed", "ipv6_redirection_supported", "rules_discarded_with_namespace_after_failure"):
        r[key] = False
    r["owned_units"] = ["cove-dns-lab-0123456789abcdef-" + x + ".service" for x in ("candidate", "original")]
    r["unit_pids"] = [100, 101]
    r["checks"] = [dict(phase=phase, assertions=count, passed=True, host_namespace_restored=True,
                        ipv6_rejections=["UDP/1/13/AccessDenied", "UDP/28/13/AccessDenied",
                                         "TCP/1/111/ConnectionRefused", "TCP/28/111/ConnectionRefused"]
                        if phase == "redirected" else [])
                   for phase, count in (("direct-candidate", 16), ("baseline", 8), ("partial-rollback", 8),
                                        ("redirected", 12), ("restored", 8), ("faults-restored", 8))]
    return value


def independent(fault):
    value = routing(); r = value["preflight_report"]
    r["scope"] = "isolated-dns-routing-v" + ("13" if fault == "crash" else "14")
    value["cleanup"]["runtime_directory_absent"] = True
    value["cleanup"]["recovery_slice_absent"] = True
    r.update(owned_slice="covedns0123456789abcdef.slice", owned_slice_removed=True)
    for key in ("independent_recovery_armed_before_rules", "independent_native_inverse_passed",
                "recovery_network_capabilities_verified", "recovery_script_manager_supplied", "prior_runtime_removed"):
        r[key] = True
    for key in (("resolver_crash_injected",) if fault == "crash" else ("resolver_frozen_verified", "requester_loss_injected")):
        r[key] = True
    r.update(controller_inverse_used=False, guardian_exit_code="0", guardian_stderr="",
             firewall_lock_hash_before="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
             firewall_lock_hash_after="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    unit = "cove-dns-lab-0123456789abcdef-rescue.service"
    r["owned_units"].append(unit); r["unit_pids"].append(102)
    r["recovery_properties"] = dict(checker.PROPERTIES, User="0", Group="0", TimeoutStopUSec="3s",
        ProtectSystem="strict", ProtectHome="yes", PrivateDevices="yes", ProtectKernelTunables="yes",
        ProtectKernelModules="yes", ProtectControlGroups="yes", StandardInput="data",
        CapabilityBoundingSet="cap_net_admin cap_net_raw", AmbientCapabilities="",
        RuntimeDirectory="cove-dns-recovery-0123456789abcdef", RuntimeDirectoryMode="0700",
        RuntimeDirectoryPreserve="yes", NetworkNamespacePath="/proc/101/ns/net", Id=unit, MainPID="102",
        FragmentPath="/run/systemd/transient/"+unit, ControlGroup="/covedns0123456789abcdef.slice/"+unit,
        Description="Cove isolated DNS recovery "+unit)
    r["checks"] = [r["checks"][1], r["checks"][3], r["checks"][4]]
    r["checks"][1]["phase"] = "guardian-active"; r["checks"][2]["phase"] = "independent-restored"
    return value


class ConfinementTests(unittest.TestCase):
    def test_valid_restricted_cases_preserve_deployment_boundary(self):
        for batch, count in ((1, 3), (2, 5)):
            result = checker.assess_permissions(permissions(batch), batch)
            self.assertEqual(result["restricted_worker_cases_passed"], count)
            self.assertTrue(result["active_capabilities_empty"])
            self.assertFalse(result["bounding_set_empty"])
            self.assertFalse(result["production_dns_qualified"])
        self.assertEqual(checker.assess_permissions(permissions(2), 2)["dns_assertions"], 237)

    def reject(self, value, batch=1):
        with self.assertRaises(ValueError):
            checker.assess_permissions(value, batch)

    def test_actual_worker_proofs_required(self):
        for k, replacement in (("active_capabilities_empty", False), ("supplementary_groups", ["201"]),
                               ("capability_bounding_set", "0000000000000000"),
                               ("filesystem_restrictions_verified", False), ("worker_uid", True)):
            value = permissions(1); value["preflight_report"]["cases"][0][k] = replacement
            self.reject(value)

    def test_each_manager_restriction_required(self):
        for key in checker.RESTRICTED:
            value = permissions(1); value["preflight_report"]["cases"][0]["properties"][key] = "other"
            self.reject(value)

    def test_cleanup_and_diagnostic_outcomes_strict(self):
        for key in permissions(1)["cleanup"]:
            value = permissions(1); value["cleanup"][key] = 1
            self.reject(value)
        for key, replacement in (("status", "stopped"), ("errors", ["failure"]), ("retained_flat_paths", ["owned"]),
                                 ("preflight_verified", False)):
            value = permissions(1); value[key] = replacement
            self.reject(value)

    def test_preservation_scope_and_deadlines_strict(self):
        for key in checker.COMMON_FALSE + ("firewall_changed", "fallback_used"):
            value = permissions(1); value["preflight_report"][key] = True
            self.reject(value)
        value = permissions(1); value["preflight_report"]["elapsed_ms"] = 22000
        self.reject(value)

    def test_changed_native_state_rejected(self):
        value = permissions(1); value["preflight_report"]["network_fingerprints_after"]["ipv4_rules"] = "b" * 64
        self.reject(value)
        value = permissions(1); value["global_identity_hashes_after"] = "other"
        self.reject(value)

    def test_missing_duplicate_or_reordered_cases(self):
        for change in (lambda x: x.pop(), lambda x: x.reverse(), lambda x: x.append(copy.deepcopy(x[0]))):
            value = permissions(2); change(value["preflight_report"]["cases"])
            self.reject(value, 2)

    def test_ownership_and_pid_ledger_strict(self):
        for key, replacement in (("worker_pid", 99999), ("unit", "other.service"), ("worker_pid", True)):
            value = permissions(1); value["preflight_report"]["cases"][0][key] = replacement
            self.reject(value)
        value = permissions(1); value["preflight_report"]["unit_pids"].pop()
        self.reject(value)

    def test_refusal_cannot_invent_successful_worker(self):
        value = permissions(2); value["preflight_report"]["cases"][2]["active_capabilities_empty"] = True
        self.reject(value, 2)

    def test_query_content_coverage_and_types_strict(self):
        for change in (lambda x: x.pop(), lambda x: x.reverse(), lambda x: x[0].update(passed=1),
                       lambda x: x[0].update(type=True), lambda x: x[0].update(blocked=1)):
            value = permissions(2); change(value["preflight_report"]["dns_checks"])
            self.reject(value, 2)

    def test_routing_success_does_not_claim_live_or_independent_recovery(self):
        result = checker.assess_routing(routing())
        self.assertEqual(result["dns_assertions"], 60)
        self.assertFalse(result["live_tv_dns_changed"])
        self.assertFalse(result["independent_recovery_qualified"])
        self.assertFalse(result["production_dns_qualified"])

    def test_routing_requires_every_native_fault_proof(self):
        for key in checker.ROUTE_FLAGS + checker.SUPERVISED_FLAGS:
            value = routing(); value["preflight_report"][key] = False
            with self.assertRaises(ValueError): checker.assess_routing(value)

    def test_namespace_disposal_does_not_count_as_inverse(self):
        value = routing(); value["preflight_report"]["rules_discarded_with_namespace_after_failure"] = True
        with self.assertRaises(ValueError): checker.assess_routing(value)

    def test_ipv6_rejection_is_separate_from_redirection(self):
        for mutate in (lambda r: r.update(ipv6_redirection_supported=True),
                       lambda r: r["checks"][3].update(ipv6_rejections=[]),
                       lambda r: r["checks"][3]["ipv6_rejections"].__setitem__(0, "UDP/1/110/TimedOut")):
            value = routing(); mutate(value["preflight_report"])
            with self.assertRaises(ValueError): checker.assess_routing(value)

    def test_restored_queries_and_host_namespace_required(self):
        for change in (lambda r: r["checks"].pop(), lambda r: r["checks"][4].update(host_namespace_restored=False),
                       lambda r: r["checks"][4].update(assertions=True)):
            value = routing(); change(value["preflight_report"])
            with self.assertRaises(ValueError): checker.assess_routing(value)

    def test_independent_inverse_is_qualified_only_inside_test_namespace(self):
        for fault in ("crash", "frozen-client"):
            result = checker.assess_independent(independent(fault), fault)
            self.assertTrue(result["isolated_independent_inverse_passed"])
            self.assertFalse(result["live_network_recovery_qualified"])
            self.assertFalse(result["production_dns_qualified"])

    def test_successful_exit_does_not_hide_script_errors(self):
        value = independent("crash"); value["preflight_report"]["guardian_stderr"] = "cannot create temporary file"
        with self.assertRaises(ValueError): checker.assess_independent(value, "crash")

    def test_independent_manager_capabilities_and_namespace_required(self):
        for key in independent("crash")["preflight_report"]["recovery_properties"]:
            value = independent("crash"); value["preflight_report"]["recovery_properties"][key] = "changed"
            with self.assertRaises(ValueError): checker.assess_independent(value, "crash")

    def test_independent_means_armed_first_and_no_controller_inverse(self):
        for key, val in (("controller_inverse_used", True), ("independent_recovery_armed_before_rules", False),
                         ("independent_native_inverse_passed", False), ("guardian_exit_code", "92")):
            value = independent("crash"); value["preflight_report"][key] = val
            with self.assertRaises(ValueError): checker.assess_independent(value, "crash")

    def test_each_fault_and_runtime_cleanup_required(self):
        for key in ("resolver_frozen_verified", "requester_loss_injected"):
            value = independent("frozen-client"); value["preflight_report"][key] = False
            with self.assertRaises(ValueError): checker.assess_independent(value, "frozen-client")
        value = independent("crash"); value["cleanup"]["runtime_directory_absent"] = False
        with self.assertRaises(ValueError): checker.assess_independent(value, "crash")

    def test_independent_requires_restored_dns_and_unchanged_lock(self):
        for change in (lambda r: r["checks"].pop(), lambda r: r.update(firewall_lock_hash_after="a" * 64),
                       lambda r: r["unit_pids"].__setitem__(2, True)):
            value = independent("crash"); change(value["preflight_report"])
            with self.assertRaises(ValueError): checker.assess_independent(value, "crash")

    def test_recovery_anchor_identity_lifetime_and_cleanup_required(self):
        for key, replacement in (("owned_slice", "foreign.slice"), ("owned_slice_removed", False)):
            value = independent("crash"); value["preflight_report"][key] = replacement
            with self.assertRaises(ValueError): checker.assess_independent(value, "crash")
        value = independent("crash"); value["cleanup"]["recovery_slice_absent"] = False
        with self.assertRaises(ValueError): checker.assess_independent(value, "crash")
        value = independent("crash")
        value["preflight_report"]["recovery_properties"]["ControlGroup"] = "/system.slice/" + value["preflight_report"]["owned_units"][2]
        with self.assertRaises(ValueError): checker.assess_independent(value, "crash")

    def test_failed_earlier_variants_cannot_qualify_by_version_substitution(self):
        for version in ("11", "12"):
            value = independent("crash"); value["preflight_report"]["scope"] = "isolated-dns-routing-v" + version
            with self.assertRaises(ValueError): checker.assess_independent(value, "crash")


if __name__ == "__main__":
    unittest.main()

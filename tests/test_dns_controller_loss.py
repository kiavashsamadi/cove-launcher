import copy
from itertools import product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_controller_loss as checker
from test_dns_confinement import independent


def controller(flow=False):
    value = independent("crash"); r = value["preflight_report"]
    r["scope"] = "isolated-dns-" + ("flow-v2" if flow else "controllerloss-v2")
    for key in checker.AUTO_FLAGS:
        r[key] = True
    r.update(observer_cleanup_used=False, primary_exit_code="0", primary_stderr="")
    r["owned_units"] += ["cove-dns-lab-0123456789abcdef-" + x + ".service" for x in ("backup", "control")]
    r["unit_pids"] += [103, 104]
    r["recovery_properties"]["RuntimeDirectoryPreserve"] = "no"
    for key, index, seconds in (("backup_recovery_properties", 3, 5), ("controller_properties", 4, 2)):
        props = dict(r["recovery_properties"])
        unit = r["owned_units"][index]
        props.update(Id=unit, MainPID=str(r["unit_pids"][index]), RuntimeMaxUSec=str(seconds)+"s",
            TimeoutStopUSec="500ms" if index == 4 else "3s", FragmentPath="/run/systemd/transient/"+unit,
            Description="Cove isolated DNS recovery "+unit, ControlGroup="/covedns0123456789abcdef.slice/"+unit,
            RuntimeDirectory="cove-dns-control-0123456789abcdef" if index == 4
            else "cove-dns-recovery-0123456789abcdef-backup")
        r[key] = props
    r["checks"].insert(2, dict(phase="primary-restored", assertions=8, passed=True,
                              host_namespace_restored=True, ipv6_rejections=[]))
    if flow:
        r.update(persistent_udp_and_tcp_filtered_before_loss=True, persistent_sockets_closed=True,
                 existing_flow_rollback_qualified=False,
                 baseline_persistent_tcp=[dict(query=i, passed=True) for i in range(2)])
        r["persistent_flow_immediate_active_repeat"] = [dict(transport=t, result="still_candidate",
            original_restored=False) for t in ("UDP", "TCP")]
        for phase in ("after_primary", "after_backup"):
            r["persistent_flow_"+phase] = [dict(transport="UDP", result="original_resolver", original_restored=True),
                dict(transport="TCP", result="IOException", original_restored=False, socket_error="ConnectionReset")]
    return value


def compatibility(version=1):
    value = controller(); r = value["preflight_report"]
    r.update(scope="live-dns-compatibility-v"+str(version), external_dns_sent=True,
             native_clients_redirected=False, raw_packet_content_retained=False,
             native_nss_before_passed=True, native_nss_after_passed=True, worker_filesystem_verified=True,
             native_upstream_count=2, native_nss_before_address_count=2, native_nss_after_address_count=2)
    r["owned_units"] = r["owned_units"][:1]; r["unit_pids"] = r["unit_pids"][:1]
    r["capture"] = dict(duration_ms=4000 if version == 1 else 6000, frames=40, discarded_frames=0,
        outgoing_queries=2, matched_replies=2, background_queries=0, probe_queries=2,
        ipv4_queries=2, ipv6_queries=0, raw_packet_content_retained=False)
    r["replay_checks"] = [dict(name_sha256="a"*64, controlled_probe=True, type=kind, tcp=tcp,
        original_rcode=0, expected_blocked=False, candidate_rcode=0, candidate_answers=2, compatible=True)
        for kind, tcp in product((1, 28), (False, True))]
    r["blocked_checks"] = [dict(ipv6=six, tcp=tcp, type=kind, passed=True)
        for six, tcp, kind in product((False, True), (False, True), (1, 28))]
    return value


def partial_primary():
    value = controller(); r = value["preflight_report"]
    r.update(scope="isolated-dns-controllerloss-v3", primary_exit_code="75",
             primary_partial_inverse_injected=True, primary_partial_inverse_observed=True)
    del r["checks"][2]
    return value


class ControllerLossTests(unittest.TestCase):
    def reject(self, value, flow=False):
        with self.assertRaises(ValueError):
            checker.assess_controller(value, flow=flow)

    def test_controller_pass_does_not_qualify_live_or_whole_session_loss(self):
        result = checker.assess_controller(controller())
        self.assertTrue(result["rule_controller_loss_passed"])
        self.assertTrue(result["automatic_native_artifact_cleanup_passed"])
        for k in ("whole_diagnostic_session_loss_tested", "live_network_recovery_qualified",
                  "production_dns_qualified", "existing_flow_rollback_qualified"):
            self.assertFalse(result[k])

    def test_all_fault_and_automatic_cleanup_proofs_required(self):
        for key in checker.AUTO_FLAGS:
            value = controller(); value["preflight_report"][key] = False; self.reject(value)
        for key in ("controller_inverse_used", "observer_cleanup_used", "host_firewall_changed"):
            value = controller(); value["preflight_report"][key] = True; self.reject(value)
        for key in controller()["cleanup"]:
            value = controller(); value["cleanup"][key] = 1; self.reject(value)

    def test_manager_deadlines_privileges_and_owned_paths_required(self):
        for name in ("recovery_properties", "backup_recovery_properties", "controller_properties"):
            for key in controller()["preflight_report"][name]:
                value = controller(); value["preflight_report"][name][key] = "other"; self.reject(value)

    def test_ownership_and_inverses_strict(self):
        for key, replacement in (("owned_units", []), ("unit_pids", [100]*5), ("owned_slice", "other.slice"),
                                 ("primary_exit_code", 0), ("primary_stderr", "warning"),
                                 ("guardian_exit_code", "1"), ("firewall_lock_hash_after", "a"*64)):
            value = controller(); value["preflight_report"][key] = replacement; self.reject(value)

    def test_missing_reordered_or_fabricated_queries_rejected(self):
        for change in (lambda rows: rows.pop(), lambda rows: rows.reverse(),
                       lambda rows: rows[0].update(assertions=True),
                       lambda rows: rows[1].update(ipv6_rejections=[])):
            value = controller(); change(value["preflight_report"]["checks"]); self.reject(value)

    def test_retained_tcp_reset_is_an_explicit_limit(self):
        result = checker.assess_controller(controller(True), flow=True)
        self.assertTrue(result["retained_tcp_reset_observed"])
        self.assertFalse(result["existing_flow_rollback_qualified"])

    def test_retained_flow_claims_require_exact_evidence(self):
        for key, replacement in (("persistent_sockets_closed", False), ("existing_flow_rollback_qualified", True),
                                 ("baseline_persistent_tcp", []), ("persistent_flow_after_backup", [])):
            value = controller(True); value["preflight_report"][key] = replacement; self.reject(value, True)
        value = controller(True)
        value["preflight_report"]["persistent_flow_after_primary"][1]["socket_error"] = "TimedOut"
        self.reject(value, True)

    def test_compatibility_versions_do_not_invent_background_coverage(self):
        for version in (1, 2):
            result = checker.assess_compatibility(compatibility(version), version)
            self.assertEqual(result["candidate_replays_passed"], 4)
            self.assertEqual(result["background_queries_observed"], 0)
            self.assertFalse(result["all_background_apps_compatible"])
            self.assertFalse(result["production_dns_qualified"])

    def test_compatibility_scope_and_cleanup_strict(self):
        for key, replacement in (("external_dns_sent", False), ("native_clients_redirected", True),
                                 ("raw_packet_content_retained", True), ("worker_filesystem_verified", False),
                                 ("native_nss_after_passed", False), ("native_upstream_count", True)):
            value = compatibility(); value["preflight_report"][key] = replacement
            with self.assertRaises(ValueError): checker.assess_compatibility(value)

    def test_capture_accounting_and_bounds_strict(self):
        for key, replacement in (("frames", 1501), ("duration_ms", True), ("matched_replies", 0),
                                 ("background_queries", 4), ("ipv6_queries", 1), ("probe_queries", -1)):
            value = compatibility(); value["preflight_report"]["capture"][key] = replacement
            with self.assertRaises(ValueError): checker.assess_compatibility(value)

    def test_replay_failures_duplicates_and_missing_transport_rejected(self):
        for change in (lambda rows: rows.pop(), lambda rows: rows.append(copy.deepcopy(rows[0])),
                       lambda rows: rows[0].update(compatible=False),
                       lambda rows: rows[0].update(candidate_rcode=3),
                       lambda rows: rows[0].update(tcp=True),
                       lambda rows: rows[0].update(name_sha256="private hostname"),
                       lambda rows: rows[0].update(controlled_probe=False)):
            value = compatibility(); change(value["preflight_report"]["replay_checks"])
            with self.assertRaises(ValueError): checker.assess_compatibility(value)

    def test_blocking_matrix_rejects_missing_or_boolean_type(self):
        for change in (lambda rows: rows.pop(), lambda rows: rows[0].update(type=True),
                       lambda rows: rows[0].update(passed=False)):
            value = compatibility(); change(value["preflight_report"]["blocked_checks"])
            with self.assertRaises(ValueError): checker.assess_compatibility(value)

    def test_invalid_selector_and_receipt_rejected(self):
        for value in (None, {}, [], {"status": "success"}):
            self.reject(value)
            with self.assertRaises(ValueError): checker.assess_compatibility(value)
        with self.assertRaises(ValueError): checker.assess_controller(controller(), flow=1)
        with self.assertRaises(ValueError): checker.assess_compatibility(compatibility(), True)

    def test_backup_completes_interrupted_primary_without_live_qualification(self):
        result = checker.assess_controller(partial_primary(), partial_primary=True)
        self.assertTrue(result["backup_completed_partial_inverse"])
        self.assertEqual(result["dns_assertions"], 28)
        self.assertFalse(result["live_network_recovery_qualified"])

    def test_partial_primary_requires_observed_failure_and_successful_backup(self):
        for key, replacement in (("primary_exit_code", "0"), ("primary_partial_inverse_injected", False),
                                 ("primary_partial_inverse_observed", False), ("guardian_exit_code", "75")):
            value = partial_primary(); value["preflight_report"][key] = replacement
            with self.assertRaises(ValueError): checker.assess_controller(value, partial_primary=True)
        with self.assertRaises(ValueError): checker.assess_controller(partial_primary(), flow=True, partial_primary=True)


if __name__ == "__main__":
    unittest.main()

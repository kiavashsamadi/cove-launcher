import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_manager as checker


def fixture(batch):
    names = checker.DEADLINE_CASES if batch == 1 else checker.RECOVERY_CASES
    r = dict(scope="isolated-dns-manager-matrix-v" + str(batch), completed=True, uid=0, euid=0,
             known_children_ended=True, resolver_file_and_firewall_unchanged=True, elapsed_ms=12000,
             network_fingerprints_before={k: "a" * 64 for k in checker.NETWORK})
    r["network_fingerprints_after"] = dict(r["network_fingerprints_before"])
    for key in ("settings_written", "firewall_changed", "external_dns_sent", "installed", "startup_changed",
                "existing_services_changed", "fallback_used", "supplementary_groups_minimized", "production_dns_qualified"):
        r[key] = False
    r.update(cases=[], owned_units=[], unit_pids=[], started_children=list(range(100, 150)))
    for index, name in enumerate(names):
        refused = name == "refused"
        parent = name in ("parentexit", "parentkill")
        planned = name in ("restart", "inverse", "functional")
        unit = "cove-dns-lab-0123456789abcdef-" + name + ".service"
        pid = 100 + index * 2
        c = dict(case=name, unit=unit, worker_pid=0 if refused else pid + int(parent), worker_uid=None if refused else 99,
                 elapsed_ms=3100 if batch == 1 else 500, supplementary_groups_minimized=False,
                 supplementary_groups=[] if refused else ["99", "201"], controller_stop_used=planned,
                 unit_and_cgroup_removed=True, ports_released=True,
                 fault_injected=(name != "deadline") if batch == 1 else not planned)
        for key in ("capabilities_empty", "no_new_privileges", "owned_cgroup_verified", "manager_properties_verified", "native_response_passed"):
            c[key] = not refused
        if batch == 1:
            c.update(request_client_loss_verified=name == "requester", stopped_worker_verified=name == "frozen")
        else:
            c["startup_refusal_observed"] = refused
        props = dict(checker.PROPERTIES)
        props.update(Id=unit, FragmentPath="/run/systemd/transient/" + unit, ControlGroup="/system.slice/" + unit,
                     Description="Cove isolated DNS recovery " + unit, MainPID=str(pid), CapabilityBoundingSet="", AmbientCapabilities="")
        c["properties"] = None if refused else props
        r["cases"].append(c)
        r["owned_units"].append(unit)
        if not refused:
            r["unit_pids"].append(pid)
            if parent:
                r["unit_pids"].append(pid + 1)
    if batch == 2:
        r["dns_checks"] = [dict(zip(("name", "type", "ipv6", "tcp", "blocked"), row), passed=True)
                           for row in checker.expected_manager_queries()]
    return dict(status="success", errors=[], root_proven=True, preflight_verified=True,
                cleanup={k: True for k in checker.CLEANUP | {"transient_units_absent"}}, retained_flat_paths=[],
                preflight_transport_result=dict(exit_code=0, timed_out=False, stderr=""),
                global_identity_hashes_before="synthetic-identity", global_identity_hashes_after="synthetic-identity",
                preflight_report=r)


class ManagerEvidenceTests(unittest.TestCase):
    def test_valid_matrix_does_not_qualify_deployment(self):
        for batch in (1, 2):
            result = checker.assess(fixture(batch), batch)
            self.assertEqual(result["isolated_manager_cases_passed"], 3 if batch == 1 else 7)
            self.assertFalse(result["supplementary_groups_minimized"])
            self.assertFalse(result["native_routing_recovery_qualified"])
            self.assertFalse(result["production_dns_qualified"])

    def reject(self, value, batch=1):
        with self.assertRaises(ValueError):
            checker.assess(value, batch)

    def test_each_cleanup_proof_required(self):
        for key in fixture(1)["cleanup"]:
            value = fixture(1)
            value["cleanup"][key] = False
            self.reject(value)

    def test_guard_stop_never_counts_as_pass(self):
        for key, replacement in (("status", "stopped"), ("root_proven", False), ("preflight_verified", False), ("errors", ["failure"])):
            value = fixture(1)
            value[key] = replacement
            self.reject(value)

    def test_scope_mutation_fallback_and_false_privilege_claim_rejected(self):
        for key in ("settings_written", "firewall_changed", "external_dns_sent", "installed", "startup_changed",
                    "existing_services_changed", "fallback_used", "supplementary_groups_minimized", "production_dns_qualified"):
            value = fixture(1)
            value["preflight_report"][key] = True
            self.reject(value)

    def test_manager_controls_required(self):
        for key in checker.PROPERTIES:
            value = fixture(1)
            value["preflight_report"]["cases"][0]["properties"][key] = "changed"
            self.reject(value)

    def test_worker_and_fault_observations_required(self):
        for index, key in ((0, "capabilities_empty"), (0, "no_new_privileges"), (1, "stopped_worker_verified"),
                           (2, "request_client_loss_verified"), (0, "unit_and_cgroup_removed"), (0, "ports_released")):
            value = fixture(1)
            value["preflight_report"]["cases"][index][key] = False
            self.reject(value)

    def test_foreign_service_cannot_be_adopted(self):
        value = fixture(1)
        value["preflight_report"]["cases"][0]["unit"] = "unrelated.service"
        self.reject(value)

    def test_network_and_identity_drift_rejected(self):
        value = fixture(1)
        value["global_identity_hashes_after"] = "changed"
        self.reject(value)
        value = fixture(1)
        value["preflight_report"]["network_fingerprints_after"]["ipv6_rules"] = "b" * 64
        self.reject(value)

    def test_missing_duplicate_or_misordered_cases_rejected(self):
        for change in (lambda x: x.pop(), lambda x: x.reverse(), lambda x: x.append(copy.deepcopy(x[0]))):
            value = fixture(2)
            change(value["preflight_report"]["cases"])
            self.reject(value, 2)

    def test_refused_start_cannot_fabricate_worker(self):
        value = fixture(2)
        value["preflight_report"]["cases"][4]["capabilities_empty"] = True
        self.reject(value, 2)

    def test_query_coverage_and_boolean_types_required(self):
        for change in (lambda x: x.pop(), lambda x: x.reverse(), lambda x: x[0].update(passed=1)):
            value = fixture(2)
            change(value["preflight_report"]["dns_checks"])
            self.reject(value, 2)

    def test_pid_and_elapsed_types_strict(self):
        for key in ("worker_pid", "elapsed_ms", "worker_uid"):
            value = fixture(1)
            value["preflight_report"]["cases"][0][key] = True
            self.reject(value)

    def test_input_bounded_and_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.json"
            for text in ('{"same":1,"same":2}', ' ' * 262145):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    checker.load(path)
            path.write_text(json.dumps(fixture(1)))
            self.assertEqual(checker.load(path), fixture(1))


if __name__ == "__main__":
    unittest.main()

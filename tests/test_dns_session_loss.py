import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_session_loss as checker
from test_dns_controller_loss import controller


def fixture():
    loss = controller(); r = loss["preflight_report"]
    loss.update(root_pid=900, loss_armed=True)
    r.update(scope="isolated-dns-sessionloss-v2", completed=False, known_children_ended=False,
             controller_pid=900, loss_armed=True, host_network_unchanged_before_loss=True,
             independent_helpers_armed_before_loss=True, primary_inverse_interruption_expected=True,
             private_baseline4="-P OUTPUT ACCEPT", private_baseline6="-P OUTPUT ACCEPT",
             private_active4="-P OUTPUT ACCEPT\n-N CVD0123456789abcdef", namespace_identity="net:[1234]")
    r["owned_units"].append("cove-dns-lab-0123456789abcdef-witness.service")
    r["unit_pids"].append(105)
    r["started_children"] = list(range(100, 120))
    r["witness_properties"] = dict(r["controller_properties"], Id=r["owned_units"][-1], MainPID="105",
                                    CapabilityBoundingSet="cap_setgid cap_setuid", RuntimeMaxUSec="7s")
    for key in ("recovery_properties", "backup_recovery_properties", "controller_properties", "witness_properties"):
        r[key]["Transient"] = "yes"
    rows = [dict(phase="identity", pid=105, controller_pid=900, uid=65534, network_namespace="net:[1234]",
                 groups_empty=True, active_capabilities_empty=True, no_new_privileges=True, bounding_startup_only=True),
            dict(phase="filtered", assertions=8, passed=True, partial=False, ipv6_rejections=checker.REJECTS),
            dict(phase="controller-dead", pidfd_observed=True),
            dict(phase="primary-partial", assertions=8, passed=True, partial=True, ipv6_rejections=[]),
            dict(phase="backup-restored", assertions=8, passed=True, partial=False, ipv6_rejections=[]),
            dict(phase="finished", completed=True)]
    loss["independent_receipts"] = {"rescue": "partial_table6_begin\n-P OUTPUT ACCEPT\npartial_table4_begin\n-P OUTPUT ACCEPT\n-N CVD0123456789abcdef\nprimary_interrupted=75\ninverse_exit=75",
        "backup": "table4_begin\n-P OUTPUT ACCEPT\ntable6_begin\n-P OUTPUT ACCEPT\ninverse_finished=0\ninverse_exit=0",
        "rescue-error": "", "backup-error": "", "witness-error": "",
        "witness": "\n".join(json.dumps(row) for row in rows)}
    launcher = "loss_wrapper_pid=800\nroot_loss_exit=137\nunmount_passwd=ok mount_id=10 absent=1\nunmount_key=ok mount_id=11 absent=1\ndiagnostic_cleanup=clean\ntarlauncher_exit=0\n"
    status = "agent_loss_signal=9 pid=900 preflight_armed=true\n"
    for pid in r["started_children"]:
        tag = "route-service" if pid in r["unit_pids"] else "manager"
        status += "read_child_started=true read=" + tag + " pid=" + str(pid) + "\n"
        if tag != "route-service":
            status += "read_child_exited=true read=" + tag + " pid=" + str(pid) + "\n"
    after = controller(); a = after["preflight_report"]
    a.update(scope="dns-postloss-read-v1", owned_units=[], unit_pids=[], started_children=[700, 701, 702, 703])
    return loss, after, launcher, status


class SessionLossTests(unittest.TestCase):
    def reject(self, args):
        with self.assertRaises(ValueError):
            checker.assess(*args)

    def test_complete_private_failure_has_limited_claims(self):
        result = checker.assess(*fixture())
        self.assertEqual(result["independent_witness_dns_assertions"], 24)
        self.assertTrue(result["host_network_preserved_across_loss"])
        self.assertFalse(result["production_dns_qualified"])
        self.assertFalse(result["physical_pc_disconnect_tested"])
        self.assertNotIn("net:[", json.dumps(result))

    def test_normal_agent_exit_is_not_loss(self):
        args = list(fixture()); args[2] = args[2].replace("exit=137", "exit=0"); self.reject(args)
        args = list(fixture()); args[3] += "agent_stopped pid=900\n"; self.reject(args)
        args = list(fixture()); args[0]["preflight_report"]["completed"] = True; self.reject(args)

    def test_partial_recovery_and_witness_cannot_be_skipped(self):
        for key in ("rescue", "backup", "witness"):
            args = fixture(); args[0]["independent_receipts"][key] = ""; self.reject(args)
        args = fixture(); args[0]["independent_receipts"]["rescue-error"] = "unexpected"; self.reject(args)
        args = fixture(); args[0]["independent_receipts"]["witness"] = args[0]["independent_receipts"]["witness"].replace('"partial": true', '"partial": false'); self.reject(args)

    def test_host_after_loss_required(self):
        args = fixture(); args[1]["preflight_report"]["network_fingerprints_after"]["ipv4_rules"] = "f" * 64; self.reject(args)
        args = fixture(); args[1]["cleanup"]["sdk_helpers_and_gates_absent"] = False; self.reject(args)
        args = fixture(); args[1]["preflight_report"]["started_children"] = []; self.reject(args)

    def test_independent_helper_restrictions(self):
        for name in ("recovery_properties", "backup_recovery_properties", "controller_properties", "witness_properties"):
            for key in ("RuntimeMaxUSec", "CapabilityBoundingSet", "NoNewPrivileges", "NetworkNamespacePath", "ProtectHome"):
                args = fixture(); args[0]["preflight_report"][name][key] = "other"; self.reject(args)

    def test_process_ledger_must_be_complete_and_not_fabricated(self):
        args = list(fixture()); args[3] += "read_child_exited=true read=unknown pid=999\n"; self.reject(args)
        args = list(fixture()); args[3] = args[3].replace("read_child_started=true read=route-service pid=105\n", ""); self.reject(args)

    def test_bounded_known_gc_trailer_only(self):
        args = fixture(); logs = args[0]["independent_receipts"]
        logs["witness"] += "\n[GC_INFO] GC_Start #1: Gen(0), Time(100 ms), Reason(0)\n[GC_INFO] GC_End #1: Gen(0), Time(104 ms)"
        self.assertEqual(checker.assess(*args)["bounded_runtime_gc_pairs"], 1)
        for suffix in ("\n{}", "\n[GC_INFO] unexpected"):
            changed = copy.deepcopy(args); changed[0]["independent_receipts"]["witness"] += suffix; self.reject(changed)


if __name__ == "__main__":
    unittest.main()

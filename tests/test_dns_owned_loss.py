import json
import unittest
from test_dns_session_loss import fixture as base_fixture
import verify_dns_session_loss as checker


def fixture():
    args = base_fixture(); loss = args[0]; r = loss["preflight_report"]
    token = "0123456789abcdef"; parent = "covedns" + token + ".slice"; child = "covedns" + token + "-client.slice"
    path = parent + "/" + child; chain = "CVD" + token
    r.update(scope="isolated-dns-owned-loss-v1", client_slice=child, client_cgroup_path=path, nonmember_unaffected=True)
    r["checks"] = [dict(phase=p, assertions=8, passed=True, host_namespace_restored=True)
                   for p in ("baseline", "nonmember-active")]
    r["private_active4"] = r["private_baseline4"] + "\n-N " + chain + "\n-A OUTPUT -m cgroup --path " + path + " -j " + chain
    for protocol in ("udp", "tcp"):
        r["private_active4"] += "\n-A " + chain + " -p " + protocol + " -m " + protocol + " --dport 53 -j REDIRECT --to-ports 1053"
    loss["independent_receipts"]["rescue"] = "partial_table6_begin\n" + r["private_baseline6"] + "\npartial_table4_begin\n" + r["private_active4"] + "\nprimary_interrupted=75\ninverse_exit=75"
    for key, index in (("recovery_properties", 2), ("backup_recovery_properties", 3), ("controller_properties", 4), ("witness_properties", 5)):
        r[key]["ControlGroup"] = "/" + (parent if index == 4 else path) + "/" + r["owned_units"][index]
    return args


class OwnedLossTests(unittest.TestCase):
    def reject(self, args):
        with self.assertRaises(ValueError):
            checker.assess(*args, owned_clients=True)

    def test_scoped_loss_retains_limits(self):
        result = checker.assess(*fixture(), owned_clients=True)
        self.assertTrue(result["owned_client_scope_verified"])
        self.assertFalse(result["live_network_recovery_qualified"])
        self.assertNotIn("0123456789abcdef", json.dumps(result))

    def test_scope_cannot_be_relabelled(self):
        self.reject(base_fixture())
        with self.assertRaises(ValueError):
            checker.assess(*fixture())

    def test_child_identity(self):
        for key in ("client_slice", "client_cgroup_path"):
            args = fixture(); args[0]["preflight_report"][key] += "other"; self.reject(args)

    def test_nonmember_proof_required(self):
        args = fixture(); args[0]["preflight_report"]["nonmember_unaffected"] = False; self.reject(args)
        for key, bad in (("assertions", 4), ("passed", False), ("host_namespace_restored", False)):
            args = fixture(); args[0]["preflight_report"]["checks"][1][key] = bad; self.reject(args)

    def test_helpers_hold_correct_group(self):
        for key in ("recovery_properties", "backup_recovery_properties", "controller_properties", "witness_properties"):
            args = fixture(); args[0]["preflight_report"][key]["ControlGroup"] = "/system.slice/foreign.service"; self.reject(args)

    def test_global_hook_and_extra_rules_rejected(self):
        for extra in ("\n-A OUTPUT -j CVD0123456789abcdef", "\n-A CVD0123456789abcdef -j RETURN"):
            args = fixture(); r = args[0]["preflight_report"]; r["private_active4"] += extra; self.reject(args)

    def test_incomplete_inverse_and_cleanup(self):
        args = fixture(); args[0]["independent_receipts"]["backup"] = ""; self.reject(args)
        args = fixture(); args[0]["cleanup"]["recovery_slice_absent"] = False; self.reject(args)


if __name__ == "__main__":
    unittest.main()

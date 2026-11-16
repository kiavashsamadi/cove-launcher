import hashlib
from itertools import product
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_native_live as checker
from test_dns_controller_loss import controller


def fixture():
    value = controller(); r = value["preflight_report"]
    r.update(scope="native-dns-live-v1", external_dns_sent=True, ordinary_clients_redirected=False,
             native_client_groups_empty=True, native_client_active_capabilities_empty=True,
             private_client_resolver_bind_only=True, existing_upstream_count=2)
    r["owned_units"] = ["cove-dns-lab-0123456789abcdef-" + s + ".service"
                        for s in ("candidate",) + tuple("live" + str(i) for i in range(8))]
    r["unit_pids"] = list(range(100, 109)); r["started_children"] = list(range(100, 120))
    r["native_checks"] = []
    for i, (six, tcp, denied) in enumerate(product((False, True), repeat=3)):
        proof = dict(pid=101+i, unit=r["owned_units"][i+1], uid=65534, network_namespace="net:[1234]",
                     groups_empty=True, active_capabilities_empty=True, no_new_privileges=True,
                     resolver_sha256=hashlib.sha256(checker.resolver(six, tcp).encode("ascii")).hexdigest())
        output = "native_identity=" + json.dumps(proof) + "\nanswer_begin"
        if not denied:
            output += "\n2001:db8::45 example.com"
        r["native_checks"].append(dict(ipv6=six, tcp=tcp, denied=denied, exit_code=2 if denied else 0,
                                       elapsed_ms=700, passed=True, answer_count=0 if denied else 1, output=output))
    return value


class LiveNativeTests(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(ValueError):
            checker.assess(value)

    def test_success_has_no_background_or_production_claim(self):
        result = checker.assess(fixture())
        self.assertEqual(result["native_real_upstream_cases_passed"], 8)
        self.assertFalse(result["background_application_compatibility_qualified"])
        self.assertFalse(result["production_dns_qualified"])
        self.assertNotIn("example.com", json.dumps(result))

    def test_scope_and_permissions(self):
        for key, bad in (("ordinary_clients_redirected", True), ("native_client_groups_empty", False),
                         ("existing_upstream_count", 0), ("host_dns_and_firewall_unchanged", False)):
            value = fixture(); value["preflight_report"][key] = bad; self.reject(value)

    def test_native_transport_order_and_answers(self):
        for key, bad in (("tcp", True), ("ipv6", 0), ("denied", None), ("exit_code", True),
                         ("answer_count", 0), ("elapsed_ms", 2001), ("passed", False)):
            value = fixture(); value["preflight_report"]["native_checks"][0][key] = bad; self.reject(value)
        value = fixture(); value["preflight_report"]["native_checks"].pop(); self.reject(value)

    def test_wrong_resolver_identity_and_capabilities(self):
        for key, bad in (("uid", 0), ("pid", 999), ("resolver_sha256", "f"*64), ("groups_empty", False),
                         ("active_capabilities_empty", False), ("network_namespace", "other")):
            value = fixture(); row = value["preflight_report"]["native_checks"][0]
            first, rest = row["output"].split("\n", 1); proof = json.loads(first[len("native_identity="):]); proof[key] = bad
            row["output"] = "native_identity=" + json.dumps(proof) + "\n" + rest; self.reject(value)

    def test_unexpected_native_output_and_incomplete_cleanup(self):
        value = fixture(); value["preflight_report"]["native_checks"][1]["output"] += "\n2001:db8::45 example.com"; self.reject(value)
        value = fixture(); value["cleanup"]["transient_units_absent"] = False; self.reject(value)


if __name__ == "__main__":
    unittest.main()

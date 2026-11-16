import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_dns_nss as checker
from test_dns_controller_loss import controller


def fixture():
    value = controller(); r = value["preflight_report"]
    r.update(scope="isolated-dns-nss-v4", native_nss_matrix_passed=True, native_client_unprivileged=True,
             private_resolver_bind_only=True, observer_inverse_used=True, native_client_groups_empty=False,
             native_client_group_count=20, native_client_production_confinement_qualified=False)
    suffixes = ("candidate", "original") + tuple("nss" + str(i) for i in range(12))
    r["owned_units"] = ["cove-dns-lab-0123456789abcdef-" + s + ".service" for s in suffixes]
    r["unit_pids"] = list(range(100, 114))
    r["started_children"] = list(range(100, 120))
    r["nss_checks"] = []
    for i, (phase, order, tcp, denied) in enumerate(checker.cases()):
        out = "proof_pid=" + str(102 + i) + "\nproof_ns=net:[1234]\n"
        out += "Uid:\t65534 65534 65534 65534\nGid:\t65534 65534 65534 65534\n"
        out += "Groups:\t" + " ".join(str(j) for j in range(1, 21)) + "\n"
        out += "".join(k + ":\t0000000000000000\n" for k in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"))
        out += "NoNewPrivs:\t1\n1:name=systemd:/system.slice/" + r["owned_units"][i + 2] + "\n"
        out += "resolver_begin\n" + checker.resolver(order, tcp) + "resolver_end\nanswer_begin"
        if not denied:
            out += "\n2001:db8::45    allowed.cove-dns.invalid"
        r["nss_checks"].append(dict(phase=phase, order=order, tcp=tcp, denied=denied,
                                   exit_code=2 if denied else 0, elapsed_ms=200, output=out))
    return value


class NativeNssTests(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(ValueError):
            checker.assess(value)

    def test_functional_coverage_is_not_production_permission_proof(self):
        result = checker.assess(fixture())
        self.assertEqual(result["native_nss_cases_passed"], 12)
        self.assertFalse(result["production_dns_qualified"])
        self.assertFalse(result["production_client_confinement_qualified"])
        self.assertNotIn("net:[", json.dumps(result))

    def test_required_order_and_transport(self):
        for key, bad in (("phase", "wrong"), ("tcp", 0), ("order", "normal"), ("denied", None),
                         ("exit_code", True), ("elapsed_ms", 3000)):
            r = fixture(); r["preflight_report"]["nss_checks"][2][key] = bad; self.reject(r)
        r = fixture(); r["preflight_report"]["nss_checks"].pop(); self.reject(r)

    def test_native_output_and_framing(self):
        for old, new in (("proof_pid=102", "proof_pid=999"), ("CapEff:\t0000000000000000", "CapEff:\t0000000000000001"),
                         ("nameserver ::1", "nameserver 192.0.2.1"), ("2001:db8::45", "2001:db8::46"),
                         ("NoNewPrivs:\t1", "NoNewPrivs:\t0"), ("answer_begin", "answer_begin\nanswer_begin")):
            r = fixture(); row = r["preflight_report"]["nss_checks"][0]; row["output"] = row["output"].replace(old, new); self.reject(r)

    def test_denied_must_have_no_answer(self):
        r = fixture(); r["preflight_report"]["nss_checks"][8]["output"] += "\n2001:db8::45"; self.reject(r)

    def test_preservation_and_limitations_required(self):
        for key, bad in (("native_client_groups_empty", True), ("native_client_group_count", True),
                         ("observer_inverse_used", False), ("worker_groups_empty", False), ("host_firewall_changed", True)):
            r = fixture(); r["preflight_report"][key] = bad; self.reject(r)
        r = fixture(); r["cleanup"]["owned_stage_removed"] = False; self.reject(r)


if __name__ == "__main__":
    unittest.main()

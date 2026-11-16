"""Check private real-upstream native lookup evidence offline; output aggregates.

These clients have private resolver-file views. Their success does not qualify
ordinary TV application interception or persistent deployment.
"""
import argparse
import hashlib
import ipaddress
from itertools import product
import json
import re

from verify_dns_confinement import envelope
from verify_dns_controller_loss import ownership
from verify_dns_manager import integer, load
from verify_dns_trial import require


def resolver(six, tcp):
    return "nameserver " + ("::1" if six else "127.0.0.54") + "\noptions timeout:1 attempts:1" + (" use-vc" if tcp else "") + "\n"


def assess(receipt):
    r = envelope(receipt, "native-dns-live-v1", runtime=True, external_dns=True)
    require(r.get("ordinary_clients_redirected") is False and r.get("host_firewall_changed") is False,
            "Ordinary-client scope differs")
    for k in ("worker_groups_empty", "worker_active_capabilities_empty", "native_client_groups_empty",
              "native_client_active_capabilities_empty", "private_client_resolver_bind_only",
              "automatic_artifact_cleanup_passed", "host_dns_and_firewall_unchanged"):
        require(r.get(k) is True, "Native permission or preservation evidence missing")
    require(integer(r.get("existing_upstream_count"), 1, 8), "Existing upstream evidence missing")
    _, units, pids = ownership(r, ("candidate",) + tuple("live" + str(i) for i in range(8)))
    rows = r.get("native_checks")
    require(isinstance(rows, list) and len(rows) == 8, "Native matrix incomplete")
    namespaces = set()
    for i, (row, (six, tcp, denied)) in enumerate(zip(rows, product((False, True), repeat=3))):
        require(isinstance(row, dict) and row.get("ipv6") is six and row.get("tcp") is tcp
                and row.get("denied") is denied and row.get("passed") is True
                and type(row.get("exit_code")) is int and row["exit_code"] == (2 if denied else 0)
                and integer(row.get("elapsed_ms"), 1, 2000), "Native case differs")
        output = row.get("output")
        require(isinstance(output, str) and len(output) <= 32768, "Native output bound")
        lines = output.splitlines()
        require(len(lines) >= 2 and lines[0].startswith("native_identity=") and lines[1] == "answer_begin",
                "Native framing differs")
        try:
            proof = json.loads(lines[0][len("native_identity="):])
        except ValueError as error:
            raise ValueError("Native identity invalid") from error
        require(isinstance(proof, dict) and proof.get("pid") == pids[i + 1] and proof.get("unit") == units[i + 1]
                and type(proof.get("uid")) is int and proof["uid"] == 65534
                and proof.get("resolver_sha256") == hashlib.sha256(resolver(six, tcp).encode("ascii")).hexdigest()
                and all(proof.get(k) is True for k in ("groups_empty", "active_capabilities_empty", "no_new_privileges")),
                "Native identity or resolver view differs")
        ns = proof.get("network_namespace")
        require(isinstance(ns, str) and re.fullmatch(r"net:\[[1-9][0-9]*\]", ns), "Native namespace absent")
        namespaces.add(ns)
        answers = [line for line in lines[2:] if line]
        require(type(row.get("answer_count")) is int and row["answer_count"] == len(answers)
                and (len(answers) == 0 if denied else 1 <= len(answers) <= 32), "Native answers differ")
        for answer in answers:
            ipaddress.ip_address(answer.split()[0])
    require(len(namespaces) == 1, "Native clients did not share the tested network")
    return dict(native_real_upstream_cases_passed=8, ipv4_ipv6_dns_transport_passed=True,
                udp_tcp_passed=True, client_groups_and_active_capabilities_empty=True,
                test_client_resolver_views_only=True, ordinary_clients_redirected=False,
                background_application_compatibility_qualified=False, production_dns_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", help="Private receipt path; raw records are never printed")
    args = parser.parse_args()
    print(json.dumps(assess(load(args.receipt)), indent=2))


if __name__ == "__main__":
    main()

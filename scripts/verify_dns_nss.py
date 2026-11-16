"""Check private native NSS fallback evidence offline; print aggregates only.

This checks consistency, not authenticity. The functional lookup clients retain
stock supplementary groups; they are not a qualified production worker design.
"""
import argparse
import json
import re

from verify_dns_confinement import envelope
from verify_dns_controller_loss import ownership
from verify_dns_manager import integer, load
from verify_dns_trial import require


def cases():
    return ([("baseline", order, tcp, False) for order in ("normal", "v6-down", "v4-down")
             for tcp in (False, True)]
            + [("filtered", "normal", tcp, denied) for denied in (False, True) for tcp in (False, True)]
            + [("restored", "normal", tcp, False) for tcp in (False, True)])


def resolver(order, tcp):
    first = "::2" if order == "v6-down" else "127.0.0.2" if order == "v4-down" else "::1"
    second = "::1" if order == "v4-down" else "127.0.0.1"
    return ("nameserver " + first + "\nnameserver " + second
            + "\noptions timeout:1 attempts:1" + (" use-vc" if tcp else "") + "\n")


def assess(receipt):
    r = envelope(receipt, "isolated-dns-nss-v4", runtime=True)
    for k in ("native_nss_matrix_passed", "native_client_unprivileged", "private_resolver_bind_only",
              "observer_inverse_used", "temporary_services_and_namespace_released", "host_dns_and_firewall_unchanged",
              "automatic_artifact_cleanup_passed", "namespace_isolated", "wrong_namespace_refused",
              "worker_groups_empty", "worker_active_capabilities_empty", "owned_slice_removed"):
        require(r.get(k) is True, "Native coverage or preservation missing")
    for k in ("host_firewall_changed", "rules_discarded_with_namespace_after_failure", "observer_cleanup_used",
              "native_client_groups_empty", "native_client_production_confinement_qualified"):
        require(r.get(k) is False, "Scope or client limitation differs")
    require(type(r.get("native_client_group_count")) is int and r["native_client_group_count"] == 20,
            "Diagnostic group limitation missing")
    _, units, pids = ownership(r, ("candidate", "original") + tuple("nss" + str(i) for i in range(12)))
    rows = r.get("nss_checks")
    require(isinstance(rows, list) and len(rows) == 12, "Native matrix incomplete")
    namespaces = set()
    for i, (row, (phase, order, tcp, denied)) in enumerate(zip(rows, cases())):
        require(isinstance(row, dict) and row.get("phase") == phase and row.get("order") == order
                and row.get("tcp") is tcp and row.get("denied") is denied
                and type(row.get("exit_code")) is int and row["exit_code"] == (2 if denied else 0)
                and integer(row.get("elapsed_ms"), 1, 2500), "Native case outcome differs")
        out = row.get("output")
        require(isinstance(out, str) and len(out) <= 32768, "Native output missing or excessive")
        require(re.findall(r"(?m)^proof_pid=(\d+)$", out) == [str(pids[i + 2])], "Client identity differs")
        ns = re.findall(r"(?m)^proof_ns=(net:\[[1-9][0-9]*\])$", out)
        require(len(ns) == 1, "Client namespace missing"); namespaces.add(ns[0])
        for key in ("Uid", "Gid"):
            require(re.search(r"(?m)^" + key + r":[ \t]+65534[ \t]+65534[ \t]+65534[ \t]+65534[ \t]*$", out),
                    "Native client identity differs")
        for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
            require(re.search(r"(?m)^" + key + r":[ \t]+0+[ \t]*$", out), "Native client capability remains")
        groups = re.findall(r"(?m)^Groups:[ \t]*([^\n]*)$", out)
        require(len(groups) == 1 and len(groups[0].split()) == 20
                and all(x.isdecimal() for x in groups[0].split())
                and re.search(r"(?m)^NoNewPrivs:[ \t]+1[ \t]*$", out), "Native client restriction differs")
        require("1:name=systemd:/system.slice/" + units[i + 2] + "\n" in out
                and "resolver_begin\n" + resolver(order, tcp) + "resolver_end\n" in out,
                "Native resolver view or ownership differs")
        marker = "\nanswer_begin"
        require(out.count(marker) == 1, "Native answer framing differs")
        answer = out.split(marker, 1)[1].strip()
        require(answer == "" if denied else re.fullmatch(r"2001:db8::45[ \t]+allowed\.cove-dns\.invalid", answer),
                "Native answer differs")
    require(len(namespaces) == 1, "Client namespaces differ")
    return dict(native_nss_cases_passed=12, ipv4_ipv6_fallback_passed=True, udp_tcp_covered=True,
                diagnostic_client_supplementary_groups=20, production_client_confinement_qualified=False,
                independent_recovery_test=False, live_clients_redirected=False, production_dns_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", help="Private receipt; raw records are never printed")
    args = parser.parse_args()
    print(json.dumps(assess(load(args.receipt)), indent=2))


if __name__ == "__main__":
    main()

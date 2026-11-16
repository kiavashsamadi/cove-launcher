"""Check private DNS confinement/recovery receipts offline; print aggregates only.

This checks evidence consistency, not authenticity. It never runs TV commands,
changes DNS or qualifies a permanent deployment.
"""
import argparse
import re

from verify_dns_manager import NETWORK, PROPERTIES, integer, load
from verify_dns_trial import CLEANUP, expected_checks, require

DEADLINES = ("deadline", "frozen", "requester")
RECOVERY = ("workercrash", "restart", "refused", "inverse", "functional")
RESTRICTED = dict(PROPERTIES, User="0", Group="0", ProtectSystem="strict", ProtectHome="yes",
                  PrivateDevices="yes", ProtectKernelTunables="yes", ProtectKernelModules="yes",
                  ProtectControlGroups="yes", UMask="0077", CapabilityBoundingSet="cap_setgid cap_setuid",
                  AmbientCapabilities="")
COMMON_FALSE = ("settings_written", "external_dns_sent", "installed", "startup_changed",
                "existing_services_changed", "production_dns_qualified")


def envelope(receipt, scope, *, runtime=False):
    require(isinstance(receipt, dict), "Receipt object required")
    require(receipt.get("status") == "success" and receipt.get("errors") == []
            and receipt.get("root_proven") is True and receipt.get("preflight_verified") is True,
            "Incomplete trial")
    cleanup = receipt.get("cleanup", {})
    require(isinstance(cleanup, dict) and set(cleanup) == CLEANUP | {"transient_units_absent"} | ({"runtime_directory_absent", "recovery_slice_absent"} if runtime else set())
            and all(v is True for v in cleanup.values()) and receipt.get("retained_flat_paths") == [],
            "Temporary cleanup incomplete")
    transport = receipt.get("preflight_transport_result", {})
    require(isinstance(transport, dict) and type(transport.get("exit_code")) is int
            and transport["exit_code"] == 0 and transport.get("timed_out") is False
            and transport.get("stderr") == "", "Transport incomplete")
    identity = receipt.get("global_identity_hashes_before")
    require(isinstance(identity, str) and bool(identity)
            and identity == receipt.get("global_identity_hashes_after"), "Identity changed")
    r = receipt.get("preflight_report", {})
    require(isinstance(r, dict) and r.get("scope") == scope and r.get("completed") is True
            and all(type(r.get(k)) is int and r[k] == 0 for k in ("uid", "euid")), "Scope differs")
    require(all(r.get(k) is False for k in COMMON_FALSE), "Deployment boundary differs")
    before = r.get("network_fingerprints_before", {})
    require(isinstance(before, dict) and set(before) == NETWORK
            and all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in before.values())
            and before == r.get("network_fingerprints_after"), "Host network changed")
    ids = r.get("started_children", [])
    require(isinstance(ids, list) and 15 <= len(ids) <= 500
            and all(integer(p, 2, 2**31 - 1) for p in ids) and len(set(ids)) == len(ids)
            and r.get("known_children_ended") is True, "Child cleanup incomplete")
    require(integer(r.get("elapsed_ms"), 1, 21999), "Diagnostic deadline exceeded")
    return r


def assess_permissions(receipt, batch):
    require(type(batch) is int and batch in (1, 2), "Unknown fixed batch")
    r = envelope(receipt, "isolated-dns-restricted-v" + str(batch))
    require(r.get("firewall_changed") is False and r.get("fallback_used") is False
            and r.get("resolver_file_and_firewall_unchanged") is True
            and r.get("supplementary_groups_minimized") is True, "Confinement proof incomplete")
    names = DEADLINES if batch == 1 else RECOVERY
    cases = r.get("cases", [])
    require(isinstance(cases, list) and len(cases) == len(names)
            and all(isinstance(c, dict) for c in cases)
            and tuple(c.get("case") for c in cases) == names, "Case coverage differs")
    tokens, units, pids = set(), [], []
    for c, name in zip(cases, names):
        refused = name == "refused"
        planned = name in ("restart", "inverse", "functional")
        unit = c.get("unit")
        require(isinstance(unit, str), "Unit string required")
        match = re.fullmatch(r"cove-dns-lab-([0-9a-f]{16})-" + name + r"\.service", unit)
        require(match is not None, "Foreign unit")
        tokens.add(match[1]); units.append(unit)
        require(c.get("controller_stop_used") is planned
                and c.get("fault_injected") is ((name != "deadline") if batch == 1 else not planned),
                "Fault or fallback evidence differs")
        require(integer(c.get("elapsed_ms"), 2500 if batch == 1 else 0, 5200 if batch == 1 else 2499),
                "Case deadline exceeded")
        require(c.get("supplementary_groups") == []
                and c.get("supplementary_groups_minimized") is (not refused)
                and c.get("capability_bounding_set") == (None if refused else "00000000000000c0"),
                "Worker permissions differ")
        for k in ("active_capabilities_empty", "filesystem_restrictions_verified", "no_new_privileges",
                  "owned_cgroup_verified", "manager_properties_verified", "native_response_passed"):
            require(c.get(k) is (not refused), "Worker proof absent")
        require(c.get("unit_and_cgroup_removed") is True and c.get("ports_released") is True,
                "Case cleanup incomplete")
        if batch == 1:
            require(c.get("request_client_loss_verified") is (name == "requester")
                    and c.get("stopped_worker_verified") is (name == "frozen"), "Fault not observed")
        else:
            require(c.get("startup_refusal_observed") is refused, "Startup result differs")
        if refused:
            require(type(c.get("worker_pid")) is int and c["worker_pid"] == 0
                    and c.get("worker_uid") is None and c.get("properties") is None,
                    "Refused startup fabricated worker")
            continue
        pid = c.get("worker_pid"); pids.append(pid)
        require(integer(pid, 2, 2**31 - 1) and pid in r["started_children"]
                and type(c.get("worker_uid")) is int and c["worker_uid"] == 99, "Worker identity differs")
        properties = c.get("properties", {})
        require(isinstance(properties, dict) and all(properties.get(k) == v for k, v in RESTRICTED.items()),
                "Manager confinement differs")
        require(properties.get("Id") == unit and properties.get("MainPID") == str(pid)
                and properties.get("FragmentPath") == "/run/systemd/transient/" + unit
                and properties.get("ControlGroup") == "/system.slice/" + unit
                and properties.get("Description") == "Cove isolated DNS recovery " + unit,
                "Manager ownership differs")
    require(len(tokens) == 1 and units == r.get("owned_units") and pids == r.get("unit_pids"),
            "Owned process/unit ledger differs")
    checks = []
    if batch == 2:
        ready = ("samsungacr.com", 1, False, False, True)
        expected = [ready] * 2 + expected_checks()[-2:] + [ready] * 2 + expected_checks()[:-2]
        checks = r.get("dns_checks", [])
        require(isinstance(checks, list) and len(checks) == len(expected), "DNS coverage incomplete")
        for c, values in zip(checks, expected):
            require(isinstance(c, dict) and c.get("passed") is True
                    and type(c.get("type")) is int
                    and all(type(c.get(k)) is bool for k in ("ipv6", "tcp", "blocked"))
                    and tuple(c.get(k) for k in ("name", "type", "ipv6", "tcp", "blocked")) == values,
                    "DNS response coverage differs")
    return dict(restricted_worker_cases_passed=len(cases), dns_assertions=len(checks) if batch == 2 else None,
                readiness_cases_passed=sum(c["case"] != "refused" for c in cases),
                supplementary_groups_empty=True, active_capabilities_empty=True,
                bounding_set_empty=False, filesystem_restrictions_verified=True,
                production_dns_qualified=False)


ROUTE_FLAGS = ("private_firewall_changed", "worker_groups_empty", "worker_active_capabilities_empty",
               "namespace_isolated", "wrong_namespace_refused", "ipv4_redirection_passed",
               "ipv6_dns_bypass_rejected", "temporary_services_and_namespace_released",
               "host_dns_and_firewall_unchanged")
SUPERVISED_FLAGS = ("partial_activation_recovered", "native_rule_inverse_passed", "idempotent_recovery_passed",
                    "partial_rule_activation_recovered", "unrelated_rules_preserved",
                    "conflicting_rule_refused_without_write", "four_inverse_interruptions_recovered")


def assess_routing(receipt):
    r = envelope(receipt, "isolated-dns-routing-v8")
    require(all(r.get(k) is True for k in ROUTE_FLAGS + SUPERVISED_FLAGS), "Native inverse proof incomplete")
    require(all(r.get(k) is False for k in ("host_firewall_changed", "ipv6_redirection_supported",
                                          "rules_discarded_with_namespace_after_failure")),
            "Isolation, IPv6 or failure boundary differs")
    expected = (("direct-candidate", 16), ("baseline", 8), ("partial-rollback", 8),
                ("redirected", 12), ("restored", 8), ("faults-restored", 8))
    checks = r.get("checks", [])
    require(isinstance(checks, list) and len(checks) == len(expected), "Routing DNS coverage incomplete")
    for c, (phase, count) in zip(checks, expected):
        require(isinstance(c, dict) and c.get("phase") == phase and type(c.get("assertions")) is int
                and c["assertions"] == count and c.get("passed") is True
                and c.get("host_namespace_restored") is True, "Native query phase differs")
        rejects = c.get("ipv6_rejections")
        require(isinstance(rejects, list) and len(rejects) == (4 if phase == "redirected" else 0),
                "IPv6 rejection evidence differs")
        if rejects:
            require(rejects == ["UDP/1/13/AccessDenied", "UDP/28/13/AccessDenied",
                                "TCP/1/111/ConnectionRefused", "TCP/28/111/ConnectionRefused"],
                    "Unknown IPv6 outcome")
    units = r.get("owned_units", []); pids = r.get("unit_pids", [])
    require(isinstance(units, list) and len(units) == 2 and isinstance(pids, list) and len(pids) == 2
            and all(integer(p, 2, 2**31 - 1) and p in r["started_children"] for p in pids)
            and len(set(pids)) == 2 and all(isinstance(u, str) for u in units),
            "Routing process ledger differs")
    match = re.fullmatch(r"cove-dns-lab-([0-9a-f]{16})-candidate\.service", units[0])
    require(match is not None and units[1] == "cove-dns-lab-" + match[1] + "-original.service", "Foreign routing service")
    return dict(isolated_native_inverse_passed=True, dns_assertions=60,
                ipv6_policy="reject-port-53", independent_recovery_qualified=False,
                live_tv_dns_changed=False, production_dns_qualified=False)


def assess_independent(receipt, fault):
    require(fault in ("crash", "frozen-client"), "Unknown fixed fault")
    version = "13" if fault == "crash" else "14"
    r = envelope(receipt, "isolated-dns-routing-v" + version, runtime=True)
    require(all(r.get(k) is True for k in ROUTE_FLAGS + (
        "independent_recovery_armed_before_rules", "independent_native_inverse_passed",
        "recovery_network_capabilities_verified", "recovery_script_manager_supplied", "prior_runtime_removed",
        "owned_slice_removed")),
        "Independent inverse proof absent")
    require(all(r.get(k) is False for k in ("host_firewall_changed", "ipv6_redirection_supported",
                                          "rules_discarded_with_namespace_after_failure", "controller_inverse_used")),
            "Isolation or independence differs")
    require(r.get("guardian_exit_code") == "0" and r.get("guardian_stderr") == "", "Recovery command failed")
    faults = ("resolver_crash_injected",) if fault == "crash" else ("resolver_frozen_verified", "requester_loss_injected")
    require(all(r.get(k) is True for k in faults), "Fault not verified")
    require(r.get("firewall_lock_hash_before") == r.get("firewall_lock_hash_after") ==
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "Firewall lock content changed")
    units, pids = r.get("owned_units", []), r.get("unit_pids", [])
    require(isinstance(units, list) and len(units) == 3 and all(isinstance(x, str) for x in units)
            and isinstance(pids, list) and len(pids) == 3
            and all(integer(p, 2, 2**31 - 1) and p in r["started_children"] for p in pids)
            and len(set(pids)) == 3, "Recovery ownership ledger differs")
    match = re.fullmatch(r"cove-dns-lab-([0-9a-f]{16})-candidate\.service", units[0])
    require(match is not None and units == ["cove-dns-lab-" + match[1] + "-" + suffix + ".service"
                                          for suffix in ("candidate", "original", "rescue")], "Foreign recovery service")
    anchor = "covedns" + match[1] + ".slice"
    require(r.get("owned_slice") == anchor, "Recovery anchor ownership differs")
    props = r.get("recovery_properties", {})
    wanted = dict(PROPERTIES, User="0", Group="0", TimeoutStopUSec="3s",
                  ProtectSystem="strict", ProtectHome="yes", PrivateDevices="yes", ProtectKernelTunables="yes",
                  ProtectKernelModules="yes", ProtectControlGroups="yes", StandardInput="data",
                  CapabilityBoundingSet="cap_net_admin cap_net_raw", AmbientCapabilities="",
                  RuntimeDirectory="cove-dns-recovery-" + match[1], RuntimeDirectoryMode="0700",
                  RuntimeDirectoryPreserve="yes", NetworkNamespacePath="/proc/" + str(pids[1]) + "/ns/net",
                  Id=units[2], MainPID=str(pids[2]), FragmentPath="/run/systemd/transient/" + units[2],
                  ControlGroup="/" + anchor + "/" + units[2], Description="Cove isolated DNS recovery " + units[2])
    require(isinstance(props, dict) and all(props.get(k) == v for k, v in wanted.items()),
            "Recovery manager restrictions differ")
    checks = r.get("checks", [])
    require(isinstance(checks, list) and len(checks) == 3, "Independent DNS coverage incomplete")
    for c, (phase, count) in zip(checks, (("baseline", 8), ("guardian-active", 12), ("independent-restored", 8))):
        require(isinstance(c, dict) and c.get("phase") == phase and type(c.get("assertions")) is int
                and c["assertions"] == count and c.get("passed") is True
                and c.get("host_namespace_restored") is True, "Independent query phase differs")
        rejects = ["UDP/1/13/AccessDenied", "UDP/28/13/AccessDenied",
                   "TCP/1/111/ConnectionRefused", "TCP/28/111/ConnectionRefused"] if phase == "guardian-active" else []
        require(c.get("ipv6_rejections") == rejects, "IPv6 outcome differs")
    return dict(isolated_independent_inverse_passed=True, verified_fault=fault, dns_assertions=28,
                live_network_recovery_qualified=False, production_dns_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deadline", required=True)
    parser.add_argument("--recovery", required=True)
    parser.add_argument("--routing")
    parser.add_argument("--independent-crash")
    parser.add_argument("--independent-frozen-client")
    args = parser.parse_args()
    import json
    result = {"deadline": assess_permissions(load(args.deadline), 1),
              "recovery": assess_permissions(load(args.recovery), 2)}
    if args.routing:
        result["routing"] = assess_routing(load(args.routing))
    if args.independent_crash:
        result["independent_crash"] = assess_independent(load(args.independent_crash), "crash")
    if args.independent_frozen_client:
        result["independent_frozen_client"] = assess_independent(load(args.independent_frozen_client), "frozen-client")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

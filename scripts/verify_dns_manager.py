"""Assess private transient-manager receipts offline; never execute TV work."""
import argparse
import json
from pathlib import Path
import re

from prepare_network_policy import unique_object
from verify_dns_trial import CLEANUP, expected_checks, require

DEADLINE_CASES = ("deadline", "frozen", "requester")
RECOVERY_CASES = ("parentexit", "parentkill", "workercrash", "restart", "refused", "inverse", "functional")
NETWORK = {"resolv_sha256", "resolv_target", "ipv4_rules", "ipv6_rules"}
PROPERTIES = {
    "LoadState": "loaded", "ActiveState": "active", "Type": "exec",
    "User": "99", "Group": "99", "SupplementaryGroups": "", "NoNewPrivileges": "yes",
    "RuntimeMaxUSec": "3s", "TimeoutStartUSec": "2s", "TimeoutStopUSec": "500ms",
    "KillMode": "control-group", "KillSignal": "9", "SendSIGKILL": "yes",
    "Restart": "no", "RemainAfterExit": "no", "CollectMode": "inactive-or-failed",
    "Transient": "yes",
}


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def expected_manager_queries():
    ready = ("samsungacr.com", 1, False, False, True)
    return [ready] * 4 + expected_checks()[-2:] + [ready] * 2 + expected_checks()[:-2]


def assess(receipt, batch):
    require(type(batch) is int and batch in (1, 2), "Unknown fixed batch")
    require(isinstance(receipt, dict), "Receipt object required")
    require(receipt.get("status") == "success" and receipt.get("errors") == []
            and receipt.get("root_proven") is True and receipt.get("preflight_verified") is True,
            "Incomplete native or controller result")
    cleanup = receipt.get("cleanup")
    require(isinstance(cleanup, dict) and set(cleanup) == CLEANUP | {"transient_units_absent"}
            and all(v is True for v in cleanup.values())
            and receipt.get("retained_flat_paths") == [], "Temporary cleanup incomplete")
    transport = receipt.get("preflight_transport_result", {})
    require(isinstance(transport, dict) and type(transport.get("exit_code")) is int
            and transport["exit_code"] == 0 and transport.get("timed_out") is False
            and transport.get("stderr") == "", "Transport did not complete")
    before_identity = receipt.get("global_identity_hashes_before")
    require(isinstance(before_identity, str) and bool(before_identity)
            and before_identity == receipt.get("global_identity_hashes_after"), "Identity drift")
    r = receipt.get("preflight_report")
    require(isinstance(r, dict) and r.get("scope") == "isolated-dns-manager-matrix-v" + str(batch)
            and r.get("completed") is True
            and all(type(r.get(k)) is int and r[k] == 0 for k in ("uid", "euid")), "Scope differs")
    for key in ("settings_written", "firewall_changed", "external_dns_sent", "installed",
                "startup_changed", "existing_services_changed", "fallback_used",
                "supplementary_groups_minimized", "production_dns_qualified"):
        require(r.get(key) is False, "Isolation or deployment boundary differs")
    require(r.get("known_children_ended") is True and r.get("resolver_file_and_firewall_unchanged") is True,
            "Process/network preservation absent")
    network = r.get("network_fingerprints_before")
    require(isinstance(network, dict) and set(network) == NETWORK
            and all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in network.values())
            and network == r.get("network_fingerprints_after"), "Network evidence differs")
    pids = r.get("started_children")
    require(isinstance(pids, list) and 15 <= len(pids) <= 180
            and all(integer(p, 2, 2**31 - 1) for p in pids) and len(set(pids)) == len(pids),
            "Process cleanup evidence differs")
    require(integer(r.get("elapsed_ms"), 1, 21999), "Diagnostic deadline exceeded")
    cases = r.get("cases")
    names = DEADLINE_CASES if batch == 1 else RECOVERY_CASES
    require(isinstance(cases, list) and len(cases) == len(names)
            and all(isinstance(c, dict) for c in cases)
            and tuple(c.get("case") for c in cases) == names, "Incomplete failure matrix")
    units, workers, packages = [], [], set()
    for c, name in zip(cases, names):
        unit = c.get("unit")
        match = re.fullmatch(r"cove-dns-lab-([0-9a-f]{16})-" + name + r"\.service", unit or "")
        require(match is not None, "Unowned unit identity")
        packages.add(match[1])
        units.append(unit)
        refused = name == "refused"
        planned = name in ("restart", "inverse", "functional")
        require(c.get("controller_stop_used") is planned
                and c.get("supplementary_groups_minimized") is False,
                "Fallback or privilege limitation hidden")
        require(integer(c.get("elapsed_ms"), 2500 if batch == 1 else 0, 5200 if batch == 1 else 2499),
                "Cleanup timing absent")
        for key in ("unit_and_cgroup_removed", "ports_released"):
            require(c.get(key) is True, "Resource cleanup absent")
        for key in ("capabilities_empty", "no_new_privileges", "owned_cgroup_verified",
                    "manager_properties_verified", "native_response_passed"):
            require(c.get(key) is (not refused), "Worker observation differs")
        if batch == 1:
            require(c.get("fault_injected") is (name != "deadline")
                    and c.get("request_client_loss_verified") is (name == "requester")
                    and c.get("stopped_worker_verified") is (name == "frozen"), "Fault evidence absent")
        else:
            require(c.get("fault_injected") is (not planned)
                    and c.get("startup_refusal_observed") is refused, "Fault evidence absent")
        if refused:
            require(c.get("worker_pid") == 0 and type(c.get("worker_pid")) is int
                    and c.get("worker_uid") is None and c.get("properties") is None
                    and c.get("supplementary_groups") == [], "Refused worker cannot be observed")
            continue
        require(type(c.get("worker_uid")) is int and c["worker_uid"] == 99
                and integer(c.get("worker_pid"), 2, 2**31 - 1) and c["worker_pid"] in pids,
                "Worker identity absent")
        groups = c.get("supplementary_groups")
        require(isinstance(groups, list) and 1 <= len(groups) <= 64
                and all(isinstance(g, str) and re.fullmatch(r"\d{1,10}", g) for g in groups)
                and len(set(groups)) == len(groups), "Observed group limitation absent")
        props = c.get("properties")
        require(isinstance(props, dict) and all(props.get(k) == v for k, v in PROPERTIES.items())
                and all(props.get(k) in ("", "0") for k in ("CapabilityBoundingSet", "AmbientCapabilities"))
                and props.get("Id") == unit and props.get("FragmentPath") == "/run/systemd/transient/" + unit
                and props.get("ControlGroup") == "/system.slice/" + unit
                and props.get("Description") == "Cove isolated DNS recovery " + unit,
                "Independent manager controls differ")
        main = props.get("MainPID")
        require(isinstance(main, str) and re.fullmatch(r"\d{1,10}", main)
                and int(main) in pids, "Manager PID absent")
        workers.append(int(main))
        if name in ("parentexit", "parentkill"):
            require(int(main) != c["worker_pid"], "Parent/child distinction absent")
            workers.append(c["worker_pid"])
        else:
            require(int(main) == c["worker_pid"], "Worker differs from service")
    require(len(packages) == 1 and r.get("owned_units") == units
            and r.get("unit_pids") == workers and len(set(workers)) == len(workers), "Unit/PID ledger differs")
    if batch == 2:
        checks = r.get("dns_checks")
        require(isinstance(checks, list) and len(checks) == 239, "Response coverage absent")
        seen = []
        for c in checks:
            require(isinstance(c, dict) and set(c) == {"name", "type", "ipv6", "tcp", "blocked", "passed"}
                    and isinstance(c["name"], str) and type(c["type"]) is int
                    and all(type(c[k]) is bool for k in ("ipv6", "tcp", "blocked"))
                    and c["passed"] is True, "Response check malformed")
            seen.append(tuple(c[k] for k in ("name", "type", "ipv6", "tcp", "blocked")))
        require(seen == expected_manager_queries(), "Response coverage differs")
    return {"isolated_manager_cases_passed": len(names), "supplementary_groups_minimized": False,
            "native_routing_recovery_qualified": False, "production_dns_qualified": False}


def load(path):
    with Path(path).open("rb") as stream:
        data = stream.read(262145)
    require(len(data) <= 262144, "Receipt too large")
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deadline", required=True)
    parser.add_argument("--recovery", required=True)
    args = parser.parse_args()
    try:
        first, second = assess(load(args.deadline), 1), assess(load(args.recovery), 2)
        print(json.dumps({"isolated_manager_cases_passed": first["isolated_manager_cases_passed"] + second["isolated_manager_cases_passed"],
                          "supplementary_groups_minimized": False, "native_routing_recovery_qualified": False,
                          "production_dns_qualified": False, "tv_contacted": False}, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print("Recovery receipt rejected; review private evidence locally.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Assess isolated DNS receipts offline. No TV access or deployment.

Valid evidence can describe a safely recovered failure. Receipt validity is
separate from test success; neither authorizes persistent DNS deployment.
"""
import argparse
from itertools import product
import json
from pathlib import Path
import re
from prepare_network_policy import unique_object

DOMAINS = (
    "samsungacr.com", "acr-eu-prd.samsungcloud.tv", "acr-us-prd.samsungcloud.tv",
    "acr0.samsungcloudsolution.com", "musicid.samsungcloudsolution.com",
    "samsungads.com", "samsungadhub.com", "adgrx.com",
)
FLAGS = (
    "worker_privileges_dropped", "no_denied_queries_forwarded",
    "upstream_outage_and_recovery_passed", "forced_resolver_stop_ports_released",
    "resolver_restart_passed", "independent_worker_deadline_passed",
    "upstream_stopped", "resolver_file_and_firewall_unchanged", "known_children_ended",
)
CLEANUP = {
    "payload_markers", "known_processes_ended", "owned_stage_removed",
    "global_identity_files_unchanged", "sdk_helpers_and_gates_absent",
}
COPY_FLAGS = (
    "temporary_binary_identical", "temporary_binary_no_capabilities",
    "temporary_binary_removed", "original_resolver_preserved",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expected_checks():
    checks = []
    for ipv6, tcp, kind in product((False, True), (False, True), (1, 28, 16)):
        for name in DOMAINS:
            for query in (name, "child." + name):
                checks.append((query, kind, ipv6, tcp, True))
        for name in ("allowed.cove-dns.invalid", "notsamsungacr.com",
                     "samsungacr.com.cove-dns.invalid"):
            checks.append((name, kind, ipv6, tcp, False))
    return checks + [
        ("SaMsUnGaCr.CoM", 1, False, False, True),
        ("samsungacr.com", 28, True, False, True),
        ("recovered.cove-dns.invalid", 1, False, False, False),
        ("restart.cove-dns.invalid", 28, True, True, False),
        ("child.samsungads.com", 16, False, True, True),
    ]


def native_report(receipt, *, passed, copied=False):
    require(isinstance(receipt, dict), "Receipt object required")
    require(receipt.get("status") == ("success" if passed else "stopped")
            and receipt.get("root_proven") is True
            and receipt.get("preflight_verified") is passed, "Diagnostic outcome differs")
    errors = receipt.get("errors")
    if passed:
        require(errors == [], "Successful trial has errors")
    else:
        require(isinstance(errors, list) and len(errors) == 1
                and isinstance(errors[0], dict)
                and errors[0].get("phase") == "diagnostic"
                and errors[0].get("type") == "RuntimeError"
                and errors[0].get("message") ==
                "Fixed isolated DNS trial failed; bounded report retained",
                "Unexpected transport or cleanup failure")
    cleanup = receipt.get("cleanup", {})
    keys = CLEANUP | ({"temporary_dns_copy_removed"} if copied else set())
    require(isinstance(cleanup, dict) and set(cleanup) == keys
            and all(value is True for value in cleanup.values())
            and receipt.get("retained_flat_paths") == [], "Temporary cleanup incomplete")
    transport = receipt.get("preflight_transport_result", {})
    require(isinstance(transport, dict) and type(transport.get("exit_code")) is int
            and transport["exit_code"] == (0 if passed else 3)
            and transport.get("timed_out") is False and transport.get("stderr") == "",
            "Diagnostic transport incomplete")
    report = receipt.get("preflight_report")
    require(isinstance(report, dict), "Native report missing")
    require(report.get("completed") is passed, "Outer and native outcomes differ")
    return report


def preserved(report, *, scope, completed, children):
    require(report.get("scope") == scope
            and all(type(report.get(k)) is int and report[k] == 0 for k in ("uid", "euid"))
            and report.get("completed") is completed, "Wrong scope/outcome")
    require(all(report.get(k) is False for k in
                ("settings_written", "firewall_changed", "external_dns_sent", "installed")),
            "Isolation proof absent")
    require(report.get("resolver_file_and_firewall_unchanged") is True
            and report.get("known_children_ended") is True, "Preservation proof absent")
    before = report.get("network_fingerprints_before")
    require(isinstance(before, dict)
            and set(before) == {"resolv_sha256", "resolv_target", "ipv4_rules", "ipv6_rules"}
            and all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v)
                    for v in before.values())
            and before == report.get("network_fingerprints_after"), "Network drift or missing evidence")
    pids = report.get("started_children")
    require(isinstance(pids, list) and len(pids) == children
            and all(type(p) is int and p > 1 for p in pids)
            and len(set(pids)) == children, "Exact child cleanup required")
    require(type(report.get("elapsed_ms")) is int and 0 < report["elapsed_ms"] < 22000,
            "Deadline exceeded")


def functional_report(report):
    preserved(report, scope="isolated-dns-runtime-trial-v3", completed=True, children=7)
    require(all(report.get(k) is True for k in FLAGS), "Runtime recovery proof absent")
    checks = report.get("checks")
    require(isinstance(checks, list), "Query list absent")
    seen = []
    for check in checks:
        require(isinstance(check, dict)
                and set(check) == {"name", "type", "ipv6", "tcp", "blocked", "passed"}
                and check["passed"] is True and isinstance(check["name"], str)
                and type(check["type"]) is int
                and all(type(check[k]) is bool for k in ("ipv6", "tcp", "blocked")),
                "Malformed query check")
        seen.append(tuple(check[k] for k in ("name", "type", "ipv6", "tcp", "blocked")))
    require(seen == expected_checks() and type(report.get("query_count")) is int
            and report["query_count"] == 233, "Incomplete query coverage")
    require(type(report.get("upstream_queries")) is int
            and 39 <= report["upstream_queries"] <= 128, "Upstream observation absent")


def recovery_report(report):
    passed = report.get("completed") is True
    preserved(report, scope="isolated-dns-parent-recovery-v1",
              completed=passed, children=8 if passed else 6)
    if not passed:
        require(report.get("phase") == "parent-exit" and report.get("cases") == []
                and report.get("error") ==
                "InvalidDataException: parent-death recovery failed; exact child fallback used",
                "Unrecognized recovery failure")
        return False
    cases = report.get("cases")
    require(isinstance(cases, list) and len(cases) == 2, "Both parent-loss cases required")
    for case, mode, code in zip(cases, ("exit", "kill"), (0, 137)):
        require(isinstance(case, dict) and case.get("mode") == mode
                and type(case.get("parent_exit_code")) is int
                and case["parent_exit_code"] == code
                and type(case.get("worker_deadline_ms")) is int
                and case["worker_deadline_ms"] == 6000, "Wrong parent fault")
        require(all(case.get(k) is True for k in
                    ("ready_before_parent_exit", "worker_identity_verified",
                     "child_exited_without_direct_signal", "ports_released")),
                "Automatic recovery not demonstrated")
        require(type(case.get("elapsed_ms")) is int and 0 <= case["elapsed_ms"] < 1700,
                "Another deadline could explain cleanup")
    return True


def copy_attempt_report(report):
    preserved(report, scope="isolated-dns-runtime-trial-v5", completed=False, children=5)
    require(all(report.get(k) is True for k in COPY_FLAGS), "Copy cleanup proof absent")
    before = report.get("original_file_capabilities_before_sha256")
    require(isinstance(before, str) and re.fullmatch("[0-9a-f]{64}", before)
            and before == report.get("original_file_capabilities_after_sha256"),
            "Original executable attributes changed")
    require(report.get("phase") == "responses" and report.get("checks") == []
            and type(report.get("query_count")) is int and report["query_count"] == 0
            and report.get("error") == "IOException: dns worker exited 85 ",
            "Unrecognized temporary-copy outcome")


def verify(functional, recovery, copy_attempt=None):
    functional_report(native_report(functional, passed=True))
    require(isinstance(recovery, dict), "Recovery receipt object required")
    parent_passed = recovery_report(
        native_report(recovery, passed=recovery.get("status") == "success"))
    if copy_attempt is not None:
        copy_attempt_report(native_report(copy_attempt, passed=False, copied=True))
    return {
        "receipts_consistent": True, "isolated_response_checks_passed": 233,
        "supervised_recovery_passed": ["upstream outage/recovery", "resolver stop/restart", "worker deadline"],
        "automatic_parent_loss_recovery_passed": parent_passed,
        "fallback_cleanup_required": not parent_passed,
        "temporary_copy_execution": "refused_and_removed" if copy_attempt is not None else "not_assessed",
        "resolver_file_and_firewall_preserved": True, "temporary_helpers_removed": True,
        "production_dns_qualified": False, "all_tracking_blocked": False,
        "limitation": "Recorded outcomes only; not receipt authenticity/freshness, production routing, persistent startup or complete telemetry prevention",
    }


def read_receipt(path):
    with path.open("rb") as stream:
        data = stream.read(1048577)
    require(len(data) <= 1048576, "Receipt exceeds size limit")
    result = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    require(isinstance(result, dict), "Receipt object required")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--functional", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--copy-attempt", type=Path)
    args = parser.parse_args()
    try:
        result = verify(read_receipt(args.functional), read_receipt(args.recovery),
                        read_receipt(args.copy_attempt) if args.copy_attempt else None)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"receipts_consistent": False,
                          "reason": "Missing, malformed or inconsistent evidence; private contents omitted"}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify private complete-agent-loss evidence and a later network read offline.

Print aggregates only. These are consistency checks, not proof of authenticity,
physical host loss, power-loss recovery, or production readiness.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from verify_dns_controller_loss import ownership, REJECTS
from verify_dns_manager import integer, load, NETWORK
from verify_dns_trial import CLEANUP, require


def outer(receipt):
    require(isinstance(receipt, dict) and receipt.get("status") == "success" and receipt.get("errors") == []
            and receipt.get("root_proven") is True and receipt.get("preflight_verified") is True,
            "Incomplete session")
    cleanup = receipt.get("cleanup")
    require(isinstance(cleanup, dict) and set(cleanup) == CLEANUP | {
        "transient_units_absent", "runtime_directory_absent", "recovery_slice_absent"}
        and all(v is True for v in cleanup.values()) and receipt.get("retained_flat_paths") == [],
        "Incomplete cleanup")
    transport = receipt.get("preflight_transport_result", {})
    require(type(transport.get("exit_code")) is int and transport["exit_code"] == 0
            and transport.get("timed_out") is False and transport.get("stderr") == "", "Transport failure")
    identity = receipt.get("global_identity_hashes_before")
    require(isinstance(identity, str) and identity and identity == receipt.get("global_identity_hashes_after"),
            "Global identity changed")
    r = receipt.get("preflight_report")
    require(isinstance(r, dict) and all(type(r.get(k)) is int and r[k] == 0 for k in ("uid", "euid")),
            "Native report missing")
    for k in ("settings_written", "host_firewall_changed", "external_dns_sent", "installed",
              "startup_changed", "existing_services_changed", "production_dns_qualified"):
        require(r.get(k) is False, "Trial scope differs")
    before = r.get("network_fingerprints_before")
    require(isinstance(before, dict) and set(before) == NETWORK
            and all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in before.values()),
            "Network baseline missing")
    require(integer(r.get("elapsed_ms"), 1, 21999), "Deadline evidence missing")
    return r


def witness_rows(text):
    require(isinstance(text, str) and len(text) <= 32768, "Witness record bound")
    body, gc, trailer = [], [], False
    for line in text.splitlines():
        if line.startswith("[GC_INFO] "):
            trailer = True; gc.append(line)
        elif line:
            require(not trailer, "Witness evidence after runtime trailer")
            body.append(line)
    require(len(gc) <= 8 and len(gc) % 2 == 0, "Incomplete runtime trailer")
    previous = 0
    for i in range(0, len(gc), 2):
        start = re.fullmatch(r"\[GC_INFO\] GC_Start #([1-9][0-9]*): Gen\(([0-2])\), Time\(([0-9]+) ms\), Reason\(([0-9]+)\)", gc[i])
        end = re.fullmatch(r"\[GC_INFO\] GC_End #([1-9][0-9]*): Gen\(([0-2])\), Time\(([0-9]+) ms\)", gc[i + 1])
        require(start and end and start.groups()[:2] == end.groups()[:2] and int(start[1]) > previous
                and 0 <= int(end[3]) - int(start[3]) <= 2000, "Unknown runtime trailer")
        previous = int(start[1])
    try:
        rows = [json.loads(line) for line in body]
    except (ValueError, TypeError) as error:
        raise ValueError("Invalid witness record") from error
    phases = ("identity", "filtered", "controller-dead", "primary-partial", "backup-restored", "finished")
    require(len(rows) == 6 and all(isinstance(row, dict) for row in rows)
            and tuple(row.get("phase") for row in rows) == phases, "Witness phases incomplete")
    return rows, len(gc) // 2


def assess(loss, after, launcher_log, agent_status):
    r, a = outer(loss), outer(after)
    require(r.get("scope") == "isolated-dns-sessionloss-v2" and r.get("completed") is False
            and r.get("known_children_ended") is False and loss.get("loss_armed") is True,
            "Expected pending loss receipt")
    for k in ("loss_armed", "namespace_isolated", "worker_groups_empty", "worker_active_capabilities_empty",
              "wrong_namespace_refused", "slice_auto_cleanup_verified", "host_network_unchanged_before_loss",
              "independent_helpers_armed_before_loss", "primary_inverse_interruption_expected"):
        require(r.get(k) is True, "Loss preparation incomplete")
    require(r.get("rules_discarded_with_namespace_after_failure") is False, "Namespace discard is not recovery")
    token, units, pids = ownership(r, ("candidate", "original", "rescue", "backup", "control", "witness"))
    root = loss.get("root_pid")
    require(integer(root, 2, 2**31 - 1) and r.get("controller_pid") == root and root not in pids,
            "Root identity differs")
    require(isinstance(launcher_log, str) and len(launcher_log) <= 65536
            and re.findall(r"root_loss_exit=(\d+)", launcher_log) == ["137"]
            and len(re.findall(r"loss_wrapper_pid=([1-9][0-9]*)", launcher_log)) == 1,
            "Expected signal exit not proved")
    for key in ("passwd", "key"):
        require(re.search(r"unmount_" + key + r"=ok mount_id=[1-9][0-9]* absent=1", launcher_log),
                "Private mount cleanup incomplete")
    require("diagnostic_cleanup=clean" in launcher_log and "tarlauncher_exit=0" in launcher_log,
            "Transport cleanup markers missing")
    require(isinstance(agent_status, str) and len(agent_status) <= 131072
            and "agent_loss_signal=9 pid=" + str(root) + " preflight_armed=true" in agent_status
            and "agent_stopped " not in agent_status and "preflight_children_exited=true" not in agent_status,
            "Agent executed an unexpected normal cleanup")
    starts = re.findall(r"read_child_started=true read=(\S+) pid=([0-9]+)", agent_status)
    ends = re.findall(r"read_child_exited=true read=(\S+) pid=([0-9]+)", agent_status)
    ids = [int(p) for _, p in starts]
    require(len(ids) <= 240 and len(set(ids)) == len(ids) and all(p > 1 for p in ids)
            and ids == r.get("started_children") and not Counter(ends) - Counter(starts)
            and Counter(starts) - Counter(ends) == Counter(("route-service", str(p)) for p in pids),
            "Loss process ledger differs")
    for key, index, seconds in (("recovery_properties", 2, 3), ("backup_recovery_properties", 3, 5),
                                ("controller_properties", 4, 2), ("witness_properties", 5, 7)):
        props = r.get(key, {})
        expected = dict(Id=units[index], MainPID=str(pids[index]), Transient="yes", NoNewPrivileges="yes",
                        RuntimeMaxUSec=str(seconds) + "s", Restart="no", CollectMode="inactive-or-failed",
                        ProtectSystem="strict", ProtectHome="yes", PrivateDevices="yes",
                        ProtectKernelTunables="yes", ProtectKernelModules="yes", ProtectControlGroups="yes",
                        NetworkNamespacePath="/proc/" + str(pids[1]) + "/ns/net")
        expected["CapabilityBoundingSet"] = "cap_setgid cap_setuid" if index == 5 else "cap_net_admin cap_net_raw"
        require(isinstance(props, dict) and all(props.get(k) == v for k, v in expected.items()),
                "Independent helper restrictions differ")
    logs = loss.get("independent_receipts", {})
    require(isinstance(logs, dict), "Independent receipts missing")
    for k in ("private_baseline4", "private_baseline6", "private_active4"):
        require(isinstance(r.get(k), str) and 1 <= len(r[k]) <= 32768, "Table receipt missing")
    require(r["private_active4"] != r["private_baseline4"], "Primary partial state not established")
    primary = "partial_table6_begin\n" + r["private_baseline6"] + "\npartial_table4_begin\n" + r["private_active4"] + "\nprimary_interrupted=75\ninverse_exit=75"
    backup = "table4_begin\n" + r["private_baseline4"] + "\ntable6_begin\n" + r["private_baseline6"] + "\ninverse_finished=0\ninverse_exit=0"
    actual = logs.get("rescue", "")
    require(isinstance(actual, str) and re.sub(r'"([A-Za-z0-9_./:-]+)"', r"\1", actual.strip()) == primary
            and logs.get("backup", "").strip() == backup
            and logs.get("rescue-error") == logs.get("backup-error") == "", "Independent inverse differs")
    require(logs.get("witness-error") in ("", "Failed open device: No such file or directory"), "Witness stderr differs")
    rows, gc_pairs = witness_rows(logs.get("witness"))
    identity = rows[0]
    require(identity.get("pid") == pids[-1] and identity.get("controller_pid") == root
            and type(identity.get("uid")) is int and identity["uid"] == 65534
            and identity.get("network_namespace") == r.get("namespace_identity")
            and all(identity.get(k) is True for k in ("groups_empty", "active_capabilities_empty",
                                                       "no_new_privileges", "bounding_startup_only")),
            "Witness identity or permissions differ")
    for i in (1, 3, 4):
        row = rows[i]
        require(type(row.get("assertions")) is int and row["assertions"] == 8 and row.get("passed") is True
                and row.get("partial") is (i == 3)
                and row.get("ipv6_rejections") == (REJECTS if i == 1 else []), "Witness query phase differs")
    require(rows[2].get("pidfd_observed") is True and rows[5].get("completed") is True, "Loss or recovery unobserved")
    require(a.get("scope") == "dns-postloss-read-v1" and a.get("completed") is True
            and a.get("known_children_ended") is True and a.get("host_dns_and_firewall_unchanged") is True
            and a.get("owned_units") == a.get("unit_pids") == [] and len(a.get("started_children", [])) == 4,
            "Separate readback incomplete")
    require(r["network_fingerprints_before"] == a["network_fingerprints_before"] == a.get("network_fingerprints_after")
            and loss["global_identity_hashes_before"] == after["global_identity_hashes_after"],
            "Host preservation across loss failed")
    return dict(complete_diagnostic_agent_loss_passed=True, primary_partial_failure_observed=True,
                backup_completed_recovery=True, independent_witness_dns_assertions=24,
                witness_active_capabilities_empty=True, automatic_native_cleanup_passed=True,
                host_network_preserved_across_loss=True, bounded_runtime_gc_pairs=gc_pairs,
                physical_pc_disconnect_tested=False, live_network_recovery_qualified=False,
                production_dns_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loss", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--launcher-log", required=True)
    parser.add_argument("--agent-status", required=True)
    args = parser.parse_args()
    print(json.dumps(assess(load(args.loss), load(args.after), Path(args.launcher_log).read_text(encoding="utf-8"),
                           Path(args.agent_status).read_text(encoding="utf-8")), indent=2))


if __name__ == "__main__":
    main()

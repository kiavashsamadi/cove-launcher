"""Verify private complete-agent-loss evidence and a later network read offline.

Print aggregates only. These are consistency checks, not proof of authenticity,
physical host loss, power-loss recovery, or production readiness.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

from verify_dns_controller_loss import ownership, REJECTS
from verify_dns_manager import integer, load, NETWORK
from verify_dns_trial import CLEANUP, require


def outer(receipt, *, owned_host=False, upstream_replay=False):
    require(not (owned_host and upstream_replay), "Choose one explicit network scope")
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
    for k in ("settings_written", "installed",
              "startup_changed", "existing_services_changed", "production_dns_qualified"):
        require(r.get(k) is False, "Trial scope differs")
    require(r.get("host_firewall_changed") is owned_host, "Host routing scope differs")
    if upstream_replay:
        require("external_dns_sent" not in r and r.get("upstream_replay_permitted") is True,
                "Replay permission is not a claim that queries were sent")
    else:
        require(r.get("external_dns_sent") is owned_host, "External DNS scope differs")
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


def assess(loss, after, launcher_log, agent_status, *, owned_clients=False, owned_host=False):
    require(not (owned_clients and owned_host), "Choose one explicit trial scope")
    r, a = outer(loss, owned_host=owned_host), outer(after)
    scope = "owned-host-dns-v2" if owned_host else (
        "isolated-dns-owned-loss-v1" if owned_clients else "isolated-dns-sessionloss-v2")
    owned_clients = owned_clients or owned_host
    require(r.get("scope") == scope and r.get("completed") is False
            and r.get("known_children_ended") is False and loss.get("loss_armed") is True,
            "Expected pending loss receipt")
    for k in ("loss_armed", "worker_groups_empty", "worker_active_capabilities_empty",
              "slice_auto_cleanup_verified",
              "independent_helpers_armed_before_loss", "primary_inverse_interruption_expected"):
        require(r.get(k) is True, "Loss preparation incomplete")
    for k in ("namespace_isolated", "host_network_unchanged_before_loss"):
        require(r.get(k) is (not owned_host), "Namespace or active host scope differs")
    if owned_host:
        for k in ("isolated_guard_refused_host", "host_activation_attempted", "existing_rules_preserved_during_activation"):
            require(r.get(k) is True, "Host activation proof missing")
        require(r.get("ordinary_clients_redirected") is False, "Ordinary apps outside trial scope")
        require(isinstance(r.get("host_boot_identity"), str)
                and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", r["host_boot_identity"]),
                "Boot identity missing")
        digest = r.get("renderer_sha256")
        require(isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest)
                and digest == a.get("renderer_sha256"), "Installed renderer changed")
    else:
        require(r.get("wrong_namespace_refused") is True, "Isolated namespace guard missing")
    require(r.get("rules_discarded_with_namespace_after_failure") is False, "Namespace discard is not recovery")
    token, units, pids = ownership(r, ("candidate", "original", "rescue", "backup", "control", "witness"))
    if owned_clients:
        child = "covedns" + token + "-client.slice"
        path = "covedns" + token + ".slice/" + child
        require(r.get("client_slice") == child and r.get("client_cgroup_path") == path
                and r.get("nonmember_unaffected") is True, "Owned client scope differs")
        checks = r.get("checks", [])
        require(isinstance(checks, list) and len(checks) == 2
                and [x.get("phase") for x in checks] == ["baseline", "nonmember-active"]
                and all(x.get("passed") is True and type(x.get("assertions")) is int
                        and x["assertions"] == 8 and x.get("host_namespace_restored") is True for x in checks),
                "Nonmember preservation incomplete")
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
        if owned_clients:
            group = path if index in (2, 3, 5) else "covedns" + token + ".slice"
            expected["ControlGroup"] = "/" + group + "/" + units[index]
        require(isinstance(props, dict) and all(props.get(k) == v for k, v in expected.items()),
                "Independent helper restrictions differ")
    logs = loss.get("independent_receipts", {})
    require(isinstance(logs, dict), "Independent receipts missing")
    for k in ("private_baseline4", "private_baseline6", "private_active4"):
        require(isinstance(r.get(k), str) and 1 <= len(r[k]) <= 32768, "Table receipt missing")
    require(r["private_active4"] != r["private_baseline4"], "Primary partial state not established")
    if owned_clients:
        chain = "CVD" + token
        additions = ["-N " + chain, "-A OUTPUT -m cgroup --path " + path + " -j " + chain]
        additions += ["-A " + chain + " -p " + p + " -m " + p + " --dport 53 -j REDIRECT --to-ports 1053"
                      for p in ("udp", "tcp")]
        require(Counter(r["private_active4"].splitlines()) == Counter(r["private_baseline4"].splitlines() + additions),
                "Unexpected scoped routing rules")
    primary = "partial_table6_begin\n" + r["private_baseline6"] + "\npartial_table4_begin\n" + r["private_active4"] + "\nprimary_interrupted=75\ninverse_exit=75"
    backup = "table4_begin\n" + r["private_baseline4"] + "\ntable6_begin\n" + r["private_baseline6"] + "\ninverse_finished=0\ninverse_exit=0"
    actual = logs.get("rescue", "")
    require(isinstance(actual, str) and re.sub(r'"([A-Za-z0-9_./:-]+)"', r"\1", actual.strip()) == primary
            and re.sub(r'"([A-Za-z0-9_./:-]+)"', r"\1", logs.get("backup", "").strip()) == backup
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
                owned_client_scope_verified=owned_clients,
                owned_client_live_network_recovery_qualified=owned_host,
                ordinary_tv_apps_qualified=False,
                physical_pc_disconnect_tested=False, live_network_recovery_qualified=False,
                production_dns_qualified=False)


def assess_reconciled_host(loss, after, reconciliation, launcher_log, agent_status, source_sha256):
    """Join a narrowly identified parser stop with separate native cleanup proof.

    The original receipt is never rewritten. A checked in-memory projection lets
    the common verifier evaluate the native phases against the same invariants.
    This is evidence consistency checking, not cryptographic attestation.
    """
    require(isinstance(loss, dict) and loss.get("status") == "stopped"
            and loss.get("errors") == [{"phase": "payload_cleanup", "type": "ValueError",
                                        "message": "backup completion or tables"}]
            and loss.get("root_proven") is True and loss.get("preflight_verified") is False
            and loss.get("loss_armed") is True, "Unexpected original failure")
    require(isinstance(source_sha256, str) and re.fullmatch("[0-9a-f]{64}", source_sha256)
            and isinstance(reconciliation, dict) and reconciliation.get("source_sha256") == source_sha256,
            "Original receipt digest differs")
    expected = {"all_known_processes_absent", "expected_signal_and_private_mount_cleanup_proved",
                "owned_units_slice_runtime_absent", "global_identity_preserved", "owned_stage_removed",
                "owned_archives_removed", "new_helpers_gates_absent"}
    cleanup = reconciliation.get("cleanup", {})
    require(reconciliation.get("status") == "clean" and reconciliation.get("errors") == []
            and reconciliation.get("root_launched") is False and reconciliation.get("settings_changed") is False
            and isinstance(cleanup, dict) and set(cleanup) == expected
            and all(v is True for v in cleanup.values()), "Separate reconciliation incomplete")
    original_cleanup = {"transient_units_absent", "runtime_directory_absent", "recovery_slice_absent",
                        "global_identity_files_unchanged", "sdk_helpers_and_gates_absent"}
    require(set(loss.get("cleanup", {})) == original_cleanup
            and all(v is True for v in loss["cleanup"].values()), "Original cleanup differs")
    native = reconciliation.get("native_assessment", {})
    require(native.get("independent_dns_assertions") == 24 and all(native.get(k) is True for k in (
        "complete_root_agent_loss_observed", "primary_partial_failure_observed", "backup_completed_both_tables",
        "witness_groups_empty", "witness_active_capabilities_empty")), "Native fault evidence incomplete")
    projected = copy.deepcopy(loss)
    projected.update(status="success", errors=[], preflight_verified=True)
    projected["cleanup"].update(payload_markers=True, known_processes_ended=True, owned_stage_removed=True)
    result = assess(projected, after, launcher_log, agent_status, owned_host=True)
    result.update(original_session_status="stopped", parser_rejection_reconciled=True,
                  original_receipt_rewritten=False, native_test_repeated=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loss", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--launcher-log", required=True)
    parser.add_argument("--agent-status", required=True)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--owned-clients", action="store_true", help="Require the isolated client-cgroup routing variant")
    scope.add_argument("--owned-host", action="store_true", help="Require the live-network owned-test-client variant")
    parser.add_argument("--reconciliation", help="Separate cleanup proof for the exact supported host parser rejection")
    args = parser.parse_args()
    logs = (Path(args.launcher_log).read_text(encoding="utf-8"), Path(args.agent_status).read_text(encoding="utf-8"))
    if args.reconciliation:
        require(args.owned_host, "Reconciliation requires explicit owned-host scope")
        result = assess_reconciled_host(load(args.loss), load(args.after), load(args.reconciliation), *logs,
                                       hashlib.sha256(Path(args.loss).read_bytes()).hexdigest())
    else:
        result = assess(load(args.loss), load(args.after), *logs, owned_clients=args.owned_clients, owned_host=args.owned_host)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

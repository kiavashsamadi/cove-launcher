"""Check private controller-loss and native DNS replay evidence offline.

No TV access, deployment or raw-record output. Consistency is not authenticity.
Live interception, whole-session loss and background-app compatibility remain
separate qualifications even when every check in a supplied receipt passes.
"""
import argparse
import json
import re
from itertools import product

from verify_dns_confinement import envelope, ROUTE_FLAGS
from verify_dns_manager import PROPERTIES, integer, load
from verify_dns_trial import require

REJECTS = ["UDP/1/13/AccessDenied", "UDP/28/13/AccessDenied",
           "TCP/1/111/ConnectionRefused", "TCP/28/111/ConnectionRefused"]
AUTO_FLAGS = ("independent_recovery_armed_before_rules", "independent_native_inverse_passed",
              "recovery_network_capabilities_verified", "recovery_script_manager_supplied",
              "owned_slice_removed", "slice_auto_cleanup_verified", "automatic_artifact_cleanup_passed",
              "rule_controller_killed", "activation_by_separate_controller", "control_runtime_absent",
              "backup_armed_before_rules", "backup_idempotent_inverse_passed")


def ownership(r, suffixes):
    units, pids = r.get("owned_units"), r.get("unit_pids")
    require(isinstance(units, list) and len(units) == len(suffixes)
            and all(isinstance(u, str) for u in units), "Unit ledger differs")
    match = re.fullmatch(r"cove-dns-lab-([0-9a-f]{16})-candidate\.service", units[0])
    require(match is not None, "Foreign candidate")
    token = match[1]
    require(units == ["cove-dns-lab-" + token + "-" + s + ".service" for s in suffixes]
            and r.get("owned_slice") == "covedns" + token + ".slice", "Foreign recovery identity")
    require(isinstance(pids, list) and len(pids) == len(suffixes)
            and all(integer(p, 2, 2**31 - 1) and p in r["started_children"] for p in pids)
            and len(set(pids)) == len(pids), "Process ledger differs")
    return token, units, pids


def assess_controller(receipt, *, flow=False, partial_primary=False, native_retry=False):
    require(type(flow) is bool and type(partial_primary) is bool and type(native_retry) is bool
            and not (flow and partial_primary) and (not native_retry or flow),
            "Fixed test selector required")
    suffix = ("libc-retry-v1" if native_retry else "flow-v2" if flow
              else "controllerloss-v3" if partial_primary else "controllerloss-v2")
    r = envelope(receipt, "isolated-dns-" + suffix, runtime=True)
    require(all(r.get(k) is True for k in ROUTE_FLAGS + AUTO_FLAGS), "Recovery proof missing")
    require(all(r.get(k) is False for k in ("host_firewall_changed", "ipv6_redirection_supported",
        "rules_discarded_with_namespace_after_failure", "controller_inverse_used", "observer_cleanup_used")),
        "Isolation or independence differs")
    for prefix in ("primary", "guardian"):
        code = "75" if prefix == "primary" and partial_primary else "0"
        require(r.get(prefix + "_exit_code") == code and r.get(prefix + "_stderr") == "", "Inverse failed")
    if partial_primary:
        require(r.get("primary_partial_inverse_injected") is True
                and r.get("primary_partial_inverse_observed") is True, "Primary fault not observed")
    require(r.get("firewall_lock_hash_before") == r.get("firewall_lock_hash_after") ==
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "Lock changed")
    token, units, pids = ownership(r, ("candidate", "original", "rescue", "backup", "control"))
    for key, index, seconds in (("recovery_properties", 2, 3), ("backup_recovery_properties", 3, 5),
                                ("controller_properties", 4, 2)):
        name = ("cove-dns-control-" if index == 4 else "cove-dns-recovery-") + token
        if index == 3:
            name += "-backup"
        wanted = dict(PROPERTIES, User="0", Group="0", RuntimeMaxUSec=str(seconds) + "s",
            TimeoutStopUSec="500ms" if index == 4 else "3s", ProtectSystem="strict", ProtectHome="yes",
            PrivateDevices="yes", ProtectKernelTunables="yes", ProtectKernelModules="yes",
            ProtectControlGroups="yes", StandardInput="data", CapabilityBoundingSet="cap_net_admin cap_net_raw",
            AmbientCapabilities="", RuntimeDirectory=name, RuntimeDirectoryMode="0700", RuntimeDirectoryPreserve="no",
            NetworkNamespacePath="/proc/" + str(pids[1]) + "/ns/net", Id=units[index], MainPID=str(pids[index]),
            FragmentPath="/run/systemd/transient/" + units[index],
            ControlGroup="/covedns" + token + ".slice/" + units[index],
            Description="Cove isolated DNS recovery " + units[index])
        actual = r.get(key)
        require(isinstance(actual, dict) and all(actual.get(k) == v for k, v in wanted.items()),
                "Manager restrictions differ")
    checks = r.get("checks")
    phases = [("baseline", 8), ("guardian-active", 12)]
    if not partial_primary:
        phases.append(("primary-restored", 8))
    phases.append(("independent-restored", 8))
    require(isinstance(checks, list) and len(checks) == len(phases), "Query coverage differs")
    for c, (phase, count) in zip(checks, phases):
        require(isinstance(c, dict) and c.get("phase") == phase and type(c.get("assertions")) is int
                and c["assertions"] == count and c.get("passed") is True
                and c.get("host_namespace_restored") is True
                and c.get("ipv6_rejections") == (REJECTS if phase == "guardian-active" else []),
                "Query phase incomplete")
    if flow:
        require(r.get("persistent_udp_and_tcp_filtered_before_loss") is True
                and r.get("persistent_sockets_closed") is True
                and r.get("existing_flow_rollback_qualified") is False, "Flow qualification differs")
        baseline = r.get("baseline_persistent_tcp")
        require(isinstance(baseline, list) and len(baseline) == 2
                and all(isinstance(x, dict) and type(x.get("query")) is int and x["query"] == i
                        and x.get("passed") is True for i, x in enumerate(baseline)), "Baseline reuse failed")
        for phase in ("immediate_active_repeat", "after_primary", "after_backup"):
            rows = r.get("persistent_flow_" + phase)
            require(isinstance(rows, list) and len(rows) == 2 and all(isinstance(x, dict) for x in rows)
                    and [x.get("transport") for x in rows] == ["UDP", "TCP"], "Flow coverage incomplete")
            if phase == "immediate_active_repeat":
                require(all(x.get("result") == "still_candidate" and x.get("original_restored") is False
                            for x in rows), "Active reuse failed")
            else:
                require(rows[0].get("result") == "original_resolver" and rows[0].get("original_restored") is True
                        and rows[1].get("result") == "IOException" and rows[1].get("original_restored") is False,
                        "Unknown retained-flow outcome")
                if phase == "after_primary":
                    require(rows[1].get("socket_error") == "ConnectionReset", "Reset not established")
    return dict(rule_controller_loss_passed=True, automatic_native_artifact_cleanup_passed=True,
                backup_idempotent_inverse_passed=True, backup_completed_partial_inverse=partial_primary,
                dns_assertions=28 if partial_primary else 36,
                retained_tcp_reset_observed=flow, existing_flow_rollback_qualified=False,
                whole_diagnostic_session_loss_tested=False, live_network_recovery_qualified=False,
                production_dns_qualified=False)


def assess_compatibility(receipt, version=1):
    require(type(version) is int and version in (1, 2), "Unknown fixed compatibility version")
    r = envelope(receipt, "live-dns-compatibility-v" + str(version), runtime=True, external_dns=True)
    require(all(r.get(k) is False for k in ("host_firewall_changed", "native_clients_redirected",
                                          "raw_packet_content_retained", "observer_cleanup_used")), "Trial scope differs")
    require(all(r.get(k) is True for k in ("host_dns_and_firewall_unchanged", "worker_groups_empty",
        "worker_active_capabilities_empty", "worker_filesystem_verified", "automatic_artifact_cleanup_passed",
        "native_nss_before_passed", "native_nss_after_passed")), "Native probe proof incomplete")
    ownership(r, ("candidate",))
    require(integer(r.get("native_upstream_count"), 1, 8)
            and all(integer(r.get("native_nss_" + t + "_address_count"), 1, 32) for t in ("before", "after")),
            "Native resolver evidence differs")
    c = r.get("capture")
    require(isinstance(c, dict) and type(c.get("duration_ms")) is int
            and c["duration_ms"] == (4000 if version == 1 else 6000)
            and c.get("raw_packet_content_retained") is False, "Capture scope differs")
    require(integer(c.get("frames"), 1, 1500) and integer(c.get("discarded_frames"), 0, c["frames"]),
            "Capture bounds differ")
    for k in ("outgoing_queries", "matched_replies", "background_queries", "probe_queries", "ipv4_queries", "ipv6_queries"):
        require(integer(c.get(k), 0, 128), "Capture count differs")
    require(c["outgoing_queries"] + c["matched_replies"] <= min(c["frames"], 128)
            and c["matched_replies"] > 0
            and c["outgoing_queries"] == c["background_queries"] + c["probe_queries"]
            == c["ipv4_queries"] + c["ipv6_queries"], "Capture accounting differs")
    rows = r.get("replay_checks")
    require(isinstance(rows, list) and 2 <= len(rows) <= 8 and len(rows) % 2 == 0, "Replay coverage differs")
    identities, background = set(), 0
    for row in rows:
        require(isinstance(row, dict), "Replay row required")
        digest = row.get("name_sha256")
        require(isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest)
                and type(row.get("type")) is int and row["type"] in (1, 28, 16)
                and all(type(row.get(k)) is bool for k in ("tcp", "controlled_probe", "expected_blocked", "compatible")),
                "Replay identity differs")
        key = (digest, row["type"], row["tcp"])
        require(key not in identities, "Duplicate replay")
        identities.add(key)
        require(integer(row.get("original_rcode"), 0, 15) and integer(row.get("candidate_rcode"), 0, 15)
                and integer(row.get("candidate_answers"), 0, 128) and row["compatible"] is True,
                "Replay failed or incomplete")
        require((row["candidate_rcode"] == 3 and row["candidate_answers"] == 0) if row["expected_blocked"]
                else row["candidate_rcode"] == row["original_rcode"], "Reply contradicts compatibility")
        background += not row["controlled_probe"]
    require(all((d, t, not tcp) in identities for d, t, tcp in identities), "Missing replay transport")
    require(not background or c["background_queries"] > 0, "Background evidence contradicted")
    blocks = r.get("blocked_checks")
    require(isinstance(blocks, list) and len(blocks) == 8, "Blocking coverage incomplete")
    for row, (six, tcp, kind) in zip(blocks, product((False, True), (False, True), (1, 28))):
        require(isinstance(row, dict) and row.get("ipv6") is six and row.get("tcp") is tcp
                and type(row.get("type")) is int and row["type"] == kind and row.get("passed") is True,
                "Blocking query differs")
    return dict(native_nss_probe_passed=True, candidate_replays_passed=len(rows),
                background_queries_observed=c["background_queries"], background_replays_passed=background,
                blocked_queries_passed=8, native_clients_redirected=False,
                all_background_apps_compatible=False, production_dns_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--flows", required=True)
    parser.add_argument("--partial-primary")
    parser.add_argument("--compatibility", required=True)
    parser.add_argument("--compatibility-version", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    result = dict(controller=assess_controller(load(args.controller)),
                  flows=assess_controller(load(args.flows), flow=True),
                  compatibility=assess_compatibility(load(args.compatibility), args.compatibility_version))
    if args.partial_primary:
        result["partial_primary"] = assess_controller(load(args.partial_primary), partial_primary=True)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

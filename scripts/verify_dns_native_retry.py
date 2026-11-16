"""Validate a private native DNS retry receipt offline; print aggregates only.

This checks consistency, not authenticity. Native libc reconnect coverage does
not establish seamless recovery for every application or for the live network.
"""
import argparse
import json
import re

from verify_dns_controller_loss import assess_controller
from verify_dns_manager import integer, load
from verify_dns_trial import require


def assess(receipt):
    assess_controller(receipt, flow=True, native_retry=True)
    r = receipt["preflight_report"]
    flags = ("native_libc_exercised", "native_active_response_passed", "native_context_closed",
             "native_primary_first_call_passed", "native_primary_second_call_passed",
             "native_backup_first_call_passed", "native_backup_second_call_passed")
    require(all(r.get(k) is True for k in flags)
            and r.get("native_test_process_unprivileged") is False, "Native coverage differs")
    rows = r.get("native_checks")
    phases = ("baseline-first", "baseline-repeat", "filtered-first", "filtered-repeat",
              "primary-first", "primary-second", "backup-first", "backup-second")
    require(isinstance(rows, list) and len(rows) == len(phases), "Native query coverage incomplete")
    sockets = []
    for row, phase in zip(rows, phases):
        require(isinstance(row, dict) and row.get("phase") == phase and row.get("success") is True
                and type(row.get("errno")) is int and row["errno"] == 0
                and type(row.get("bytes")) is int and row["bytes"] == (32 if phase.startswith("filtered") else 48)
                and integer(row.get("elapsed_ms"), 0, 1400), "Native query failed or contradicted")
        socket = row.get("socket_identity")
        require(isinstance(socket, str) and re.fullmatch(r"socket:\[[1-9][0-9]*\]", socket) is not None,
                "Native connection identity missing")
        sockets.append(socket)
    require(sockets[0] == sockets[1] and sockets[2] == sockets[3]
            and sockets[2] != sockets[4] and len(set(sockets[4:])) == 1,
            "Reuse and reconnect are not established")
    return dict(native_queries_passed=8, native_first_call_reconnected=True,
                native_connection_reused_after_recovery=True, raw_tcp_reset_still_observed=True,
                native_test_process_unprivileged=False, all_native_clients_qualified=False,
                live_network_recovery_qualified=False, production_dns_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", help="Private receipt path; its contents are never printed")
    args = parser.parse_args()
    print(json.dumps(assess(load(args.receipt)), indent=2))


if __name__ == "__main__":
    main()

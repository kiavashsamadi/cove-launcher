"""Check private passive-DNS evidence offline; print aggregates, never identifiers.

This does not contact the TV or prove all traffic was captured or classified.
"""
import argparse
import json
from pathlib import Path
import re

from verify_dns_session_loss import outer
from verify_dns_manager import load
from verify_dns_trial import require


def observation_rows(text):
    require(isinstance(text, str) and len(text.encode()) <= 16384, "Observer output bound")
    body, gc, trailer = [], [], False
    for line in text.splitlines():
        if line.startswith("[GC_INFO] "):
            trailer = True; gc.append(line)
        elif line:
            require(not trailer, "Observation after runtime trailer")
            body.append(line)
    require(len(gc) <= 80 and len(gc) % 2 == 0, "Runtime trailer bound")
    previous = 0
    for i in range(0, len(gc), 2):
        start = re.fullmatch(r"\[GC_INFO\] GC_Start #([1-9][0-9]*): Gen\(([0-2])\), Time\(([0-9]+) ms\), Reason\(([0-9]+)\)", gc[i])
        end = re.fullmatch(r"\[GC_INFO\] GC_End #([1-9][0-9]*): Gen\(([0-2])\), Time\(([0-9]+) ms\)", gc[i + 1])
        require(start and end and start.groups()[:2] == end.groups()[:2] and int(start[1]) > previous
                and 0 <= int(end[3]) - int(start[3]) <= 2000, "Runtime pair differs")
        previous = int(start[1])
    require(len(body) == 2, "Observation phases incomplete")
    rows = [json.loads(line) for line in body]
    require(all(isinstance(x, dict) for x in rows) and rows[0].get("phase") == "identity"
            and rows[1].get("phase") == "finished", "Observation phases differ")
    return rows, len(gc) // 2


def assess(observation, after, *, replay=False):
    r, a = outer(observation, upstream_replay=replay), outer(after)
    require(r.get("scope") == ("passive-replay-v1" if replay else "passive-observer-v1") and r.get("completed") is False
            and r.get("observer_armed") is True and r.get("known_children_ended") is False
            and r.get("command_children_ended") is True and r.get("observer_permissions_verified") is True
            and r.get("ordinary_clients_redirected") is False, "Observer scope differs")
    units, pids = r.get("owned_units"), r.get("unit_pids")
    count = 2 if replay else 1
    require(isinstance(units, list) and len(units) == count and isinstance(units[-1], str)
            and re.fullmatch(r"cove-dns-lab-[0-9a-f]{16}-control\.service", units[-1])
            and isinstance(pids, list) and len(pids) == count and len(set(pids)) == count
            and all(type(p) is int and p > 1 for p in pids),
            "Observer ownership missing")
    if replay:
        require(units[0] == units[1].replace("-control.service", "-candidate.service")
                and r.get("deferred_worker_pids") == pids
                and all(r.get(k) is True for k in ("candidate_uid_dropped", "candidate_groups_empty",
                    "candidate_active_capabilities_empty")), "Replay candidate ownership/restrictions missing")
    props = r.get("observer_properties", {})
    expected = dict(Id=units[-1], MainPID=str(pids[-1]), Transient="yes", Restart="no", NoNewPrivileges="yes",
        CapabilityBoundingSet="cap_setgid cap_setuid cap_net_raw", ProtectSystem="strict", ProtectHome="yes",
        PrivateDevices="yes", ProtectKernelTunables="yes", ProtectKernelModules="yes", ProtectControlGroups="yes",
        ControlGroup="/system.slice/" + units[-1], NetworkNamespacePath="/proc/1/ns/net")
    require(isinstance(props, dict) and all(props.get(k) == v for k, v in expected.items())
            and props.get("RuntimeMaxUSec") in ("75s", "1min 15s"), "Observer restrictions differ")
    rows, gc = observation_rows(observation.get("observer_receipt"))
    identity, sample = rows
    require(identity == r.get("observer_identity") and identity.get("pid") == pids[-1]
            and identity.get("unit") == units[-1] and type(identity.get("uid")) is int and identity["uid"] == 65534
            and all(identity.get(k) is True for k in ("groups_empty", "active_capabilities_empty", "no_new_privileges",
                "filesystem_read_only", "packet_socket_opened_before_drop")), "Observed privilege drop missing")
    require(observation.get("observer_error") in ("", "Failed open device: No such file or directory"),
            "Observer error differs")
    for key in ("raw_packet_content_retained", "query_names_retained", "addresses_retained",
                "ordinary_app_compatibility_qualified", "frame_limit_reached"):
        require(sample.get(key) is False, "Passive scope/privacy differs")
    for key in ("frames", "discarded_frames", "queries", "paired_replies", "unpaired_capacity_drops",
                "blocked_name_queries", "other_name_queries", "ipv4_queries", "ipv6_queries", "elapsed_ms"):
        require(type(sample.get(key)) is int and sample[key] >= 0, "Invalid observation counter")
    require(sample.get("completed") is True and 59000 <= sample["elapsed_ms"] <= 70000
            and sample["frames"] <= 30000 and sample["queries"] <= sample["frames"]
            and sample["queries"] == sample["blocked_name_queries"] + sample["other_name_queries"]
            and sample["queries"] == sample["ipv4_queries"] + sample["ipv6_queries"]
            and sample["paired_replies"] <= sample["queries"]
            and sample["unpaired_capacity_drops"] <= sample["queries"]
            and sample["discarded_frames"] <= sample["frames"], "Sample accounting differs")
    replayed = validate_replay(sample) if replay else 0
    if not replay:
        require(sample.get("sent_queries") is False, "Passive observer sent queries")
    require(a.get("scope") == "dns-postloss-read-v1" and a.get("completed") is True
            and a.get("host_dns_and_firewall_unchanged") is True and a.get("known_children_ended") is True
            and a.get("owned_units") == a.get("unit_pids") == [] and len(a.get("started_children", [])) == 4,
            "Separate readback incomplete")
    require(r["network_fingerprints_before"] == r.get("network_fingerprints_after_arming")
            == a["network_fingerprints_before"] == a.get("network_fingerprints_after")
            and observation["global_identity_hashes_before"] == after["global_identity_hashes_after"],
            "Network or global identity changed")
    digest = r.get("renderer_sha256")
    require(isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest)
            and digest == a.get("renderer_sha256"), "Renderer changed")
    return dict(passive_observation_verified=True, replay_scope=replay,
        replayed_questions=replayed, replay_checks_passed=replayed * 4,
        background_replay_coverage_observed=bool(replayed), duration_ms=sample["elapsed_ms"],
        background_dns_queries=sample["queries"], paired_replies=sample["paired_replies"],
        ipv4_queries=sample["ipv4_queries"], ipv6_queries=sample["ipv6_queries"],
        configured_blocklist_name_queries=sample["blocked_name_queries"],
        unpaired_capacity_drops=sample["unpaired_capacity_drops"], bounded_runtime_gc_pairs=gc,
        host_network_and_renderer_preserved=True, raw_packets_or_names_retained=False,
        ordinary_app_compatibility_qualified=False, all_telemetry_absent_proved=False, production_dns_qualified=False)


def validate_replay(sample):
    checks, skipped = sample.get("replay_checks"), sample.get("unconfigured_replay_pairs_skipped")
    require(isinstance(checks, list) and len(checks) <= 16 and len(checks) % 4 == 0
            and type(skipped) is int and 0 <= skipped <= 4
            and sample.get("sent_queries") is bool(checks), "Replay bound or sent-query accounting differs")
    count = len(checks) // 4
    require(count + skipped <= min(4, sample["paired_replies"]), "Unobserved questions replayed")
    fields = {"question_index", "ipv6", "tcp", "type", "blocked", "original_rcode", "original_answers",
              "candidate_rcode", "candidate_answers", "passed"}
    for i in range(count):
        batch = checks[i * 4:i * 4 + 4]
        require(all(isinstance(x, dict) and set(x) == fields for x in batch), "Unexpected replay fields")
        require([(x["ipv6"], x["tcp"]) for x in batch] == [(False, False), (False, True), (True, False), (True, True)],
                "Replay transport matrix incomplete")
        for x in batch:
            require(type(x["question_index"]) is int and x["question_index"] == i
                    and type(x["type"]) is int and x["type"] in (1, 28, 16)
                    and all(type(x[k]) is bool for k in ("blocked", "ipv6", "tcp")) and x["passed"] is True,
                    "Replay result invalid")
            for key in ("original_rcode", "candidate_rcode", "original_answers", "candidate_answers"):
                require(type(x[key]) is int and 0 <= x[key] <= (15 if key.endswith("rcode") else 65535),
                        "DNS result shape invalid")
            require((x["candidate_rcode"] == 3 and x["candidate_answers"] == 0) if x["blocked"] else
                    (x["candidate_rcode"] == x["original_rcode"] and (x["original_answers"] == 0 or x["candidate_answers"] > 0)),
                    "Replayed response differs")
        require(all((x["type"], x["blocked"], x["original_rcode"], x["original_answers"]) ==
                    (batch[0]["type"], batch[0]["blocked"], batch[0]["original_rcode"], batch[0]["original_answers"])
                    for x in batch), "Different original question across transports")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--replay", action="store_true", help="Explicit bounded replay scope; no ordinary apps redirected")
    args = parser.parse_args()
    print(json.dumps(assess(load(args.observation), load(args.after), replay=args.replay), indent=2))

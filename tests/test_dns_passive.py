import copy
import json
import unittest
from test_dns_session_loss import fixture as session_fixture
import verify_dns_passive as checker


def fixture():
    after = session_fixture()[1]; observation = copy.deepcopy(after)
    r = observation["preflight_report"]
    unit = "cove-dns-lab-0123456789abcdef-control.service"
    identity = dict(phase="identity", pid=123, uid=65534, unit=unit, network_namespace="net:[1234]",
        groups_empty=True, active_capabilities_empty=True, no_new_privileges=True,
        filesystem_read_only=True, packet_socket_opened_before_drop=True)
    r.update(scope="passive-observer-v1", completed=False, observer_armed=True, known_children_ended=False,
        command_children_ended=True, observer_permissions_verified=True, ordinary_clients_redirected=False,
        owned_units=[unit], unit_pids=[123], renderer_sha256="a" * 64, observer_identity=identity,
        network_fingerprints_after_arming=dict(r["network_fingerprints_before"]))
    r["observer_properties"] = dict(Id=unit, MainPID="123", Transient="yes", Restart="no", NoNewPrivileges="yes",
        CapabilityBoundingSet="cap_setgid cap_setuid cap_net_raw", ProtectSystem="strict", ProtectHome="yes",
        PrivateDevices="yes", ProtectKernelTunables="yes", ProtectKernelModules="yes", ProtectControlGroups="yes",
        ControlGroup="/system.slice/" + unit, NetworkNamespacePath="/proc/1/ns/net", RuntimeMaxUSec="1min 15s")
    sample = dict(phase="finished", completed=True, elapsed_ms=60010, frames=20, discarded_frames=0,
        queries=2, paired_replies=2, unpaired_capacity_drops=0, blocked_name_queries=0, other_name_queries=2,
        ipv4_queries=2, ipv6_queries=0, frame_limit_reached=False, raw_packet_content_retained=False,
        query_names_retained=False, addresses_retained=False, sent_queries=False, ordinary_app_compatibility_qualified=False)
    observation["observer_receipt"] = json.dumps(identity) + "\n" + json.dumps(sample)
    observation["observer_error"] = ""
    after["preflight_report"]["renderer_sha256"] = "a" * 64
    return observation, after


def modify_sample(args, key, value):
    rows = [json.loads(x) for x in args[0]["observer_receipt"].splitlines()]
    rows[1][key] = value
    args[0]["observer_receipt"] = "\n".join(json.dumps(x) for x in rows)


class PassiveTests(unittest.TestCase):
    def reject(self, args):
        with self.assertRaises(ValueError): checker.assess(*args)

    def test_narrow_observation_and_no_identifiers(self):
        result = checker.assess(*fixture())
        self.assertEqual(result["background_dns_queries"], 2)
        self.assertFalse(result["ordinary_app_compatibility_qualified"])
        self.assertFalse(result["all_telemetry_absent_proved"])
        for value in ("0123456789abcdef", "net:[", "service"):
            self.assertNotIn(value, json.dumps(result))

    def test_zero_background_is_not_no_telemetry(self):
        args = fixture()
        for key in ("queries", "paired_replies", "other_name_queries", "ipv4_queries"):
            modify_sample(args, key, 0)
        self.assertFalse(checker.assess(*args)["all_telemetry_absent_proved"])

    def test_scope_and_privilege(self):
        for key in ("host_firewall_changed", "external_dns_sent", "ordinary_clients_redirected"):
            args = fixture(); args[0]["preflight_report"][key] = True; self.reject(args)
        args = fixture(); args[0]["preflight_report"]["observer_properties"]["CapabilityBoundingSet"] += " cap_net_admin"; self.reject(args)

    def test_complete_duration_and_counter_accounting(self):
        for key, value in (("elapsed_ms", 1000), ("frames", 30001), ("queries", True), ("paired_replies", 3),
                           ("unpaired_capacity_drops", 3), ("ipv6_queries", 1), ("frame_limit_reached", True)):
            args = fixture(); modify_sample(args, key, value); self.reject(args)

    def test_no_raw_data_claim_or_queries(self):
        for key in ("raw_packet_content_retained", "query_names_retained", "addresses_retained", "sent_queries"):
            args = fixture(); modify_sample(args, key, True); self.reject(args)

    def test_runtime_trailer_is_bounded(self):
        args = fixture()
        gc = "".join("\n[GC_INFO] GC_Start #" + str(i) + ": Gen(0), Time(100 ms), Reason(0)\n"
                     "[GC_INFO] GC_End #" + str(i) + ": Gen(0), Time(105 ms)" for i in range(1, 31))
        args[0]["observer_receipt"] += gc
        self.assertEqual(checker.assess(*args)["bounded_runtime_gc_pairs"], 30)
        args[0]["observer_receipt"] += "\n{}"; self.reject(args)

    def test_cleanup_and_postread_required(self):
        args = fixture(); args[0]["cleanup"]["owned_stage_removed"] = False; self.reject(args)
        args = fixture(); args[1]["preflight_report"]["renderer_sha256"] = "b" * 64; self.reject(args)
        args = fixture(); args[1]["preflight_report"]["network_fingerprints_after"]["ipv6_rules"] = "b" * 64; self.reject(args)

    def test_missing_identity_and_unexpected_stderr(self):
        args = fixture(); args[0]["observer_receipt"] = "{}"; self.reject(args)
        args = fixture(); args[0]["observer_error"] = "unexpected"; self.reject(args)


if __name__ == "__main__":
    unittest.main()

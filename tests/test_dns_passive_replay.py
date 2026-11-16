import copy
import json
import unittest
from test_dns_passive import fixture as passive_fixture
import verify_dns_passive as checker


def fixture(*, questions=1):
    args = passive_fixture()
    r = args[0]["preflight_report"]
    r.pop("external_dns_sent")
    r.update(scope="passive-replay-v1", upstream_replay_permitted=True,
        candidate_uid_dropped=True, candidate_groups_empty=True, candidate_active_capabilities_empty=True)
    r["owned_units"].insert(0, r["owned_units"][0].replace("-control.service", "-candidate.service"))
    r["unit_pids"].insert(0, 122)
    r["deferred_worker_pids"] = list(r["unit_pids"])
    rows = [json.loads(x) for x in args[0]["observer_receipt"].splitlines()]
    sample = rows[1]
    sample.update(replay_checks=[], unconfigured_replay_pairs_skipped=0, sent_queries=bool(questions))
    for i in range(questions):
        for ipv6, tcp in ((False, False), (False, True), (True, False), (True, True)):
            sample["replay_checks"].append(dict(question_index=i, ipv6=ipv6, tcp=tcp, type=1, blocked=False,
                original_rcode=0, original_answers=1, candidate_rcode=0, candidate_answers=2, passed=True))
    args[0]["observer_receipt"] = "\n".join(json.dumps(x) for x in rows)
    return args


def edit(args, callback):
    rows = [json.loads(x) for x in args[0]["observer_receipt"].splitlines()]
    callback(rows[1])
    args[0]["observer_receipt"] = "\n".join(json.dumps(x) for x in rows)


class ReplayTests(unittest.TestCase):
    def reject(self, args):
        with self.assertRaises(ValueError): checker.assess(*args, replay=True)

    def test_explicit_scope_and_limited_coverage(self):
        args = fixture()
        result = checker.assess(*args, replay=True)
        self.assertEqual(result["replay_checks_passed"], 4)
        self.assertTrue(result["background_replay_coverage_observed"])
        self.assertFalse(result["ordinary_app_compatibility_qualified"])
        with self.assertRaises(ValueError): checker.assess(*args)
        self.reject(passive_fixture())

    def test_empty_sample_is_not_compatibility(self):
        result = checker.assess(*fixture(questions=0), replay=True)
        self.assertEqual(result["replay_checks_passed"], 0)
        self.assertFalse(result["background_replay_coverage_observed"])
        self.assertFalse(result["production_dns_qualified"])

    def test_no_mixed_or_invented_scope(self):
        for key, value in (("external_dns_sent", False), ("upstream_replay_permitted", False),
                           ("host_firewall_changed", True), ("ordinary_clients_redirected", True)):
            args = fixture(); args[0]["preflight_report"][key] = value; self.reject(args)

    def test_candidate_ownership_and_drop(self):
        for key in ("candidate_uid_dropped", "candidate_groups_empty", "candidate_active_capabilities_empty"):
            args = fixture(); args[0]["preflight_report"][key] = False; self.reject(args)
        args = fixture(); args[0]["preflight_report"]["deferred_worker_pids"] = [122]; self.reject(args)
        args = fixture(); args[0]["preflight_report"]["owned_units"][0] = "foreign.service"; self.reject(args)

    def test_transport_matrix_and_same_question(self):
        for key, value in (("tcp", True), ("ipv6", True), ("question_index", 1), ("type", 28), ("passed", False)):
            args = fixture(); edit(args, lambda s: s["replay_checks"][0].update({key: value})); self.reject(args)

    def test_bounds_and_no_raw_identifiers(self):
        for key, value in (("query_name", "private.invalid"), ("original_rcode", 16), ("candidate_answers", -1)):
            args = fixture(); edit(args, lambda s: s["replay_checks"][0].update({key: value})); self.reject(args)
        args = fixture(); edit(args, lambda s: s.update(sent_queries=False)); self.reject(args)
        args = fixture(); edit(args, lambda s: s.update(unconfigured_replay_pairs_skipped=4)); self.reject(args)
        args = fixture(); edit(args, lambda s: s["replay_checks"].pop()); self.reject(args)

    def test_response_mismatch(self):
        for key, value in (("candidate_rcode", 3), ("candidate_answers", 0)):
            args = fixture(); edit(args, lambda s: s["replay_checks"][0].update({key: value})); self.reject(args)

    def test_expected_nxdomain_is_not_upstream_success(self):
        args = fixture()
        edit(args, lambda s: [x.update(blocked=True, candidate_rcode=3, candidate_answers=0) for x in s["replay_checks"]])
        self.assertEqual(checker.assess(*args, replay=True)["replay_checks_passed"], 4)
        edit(args, lambda s: s["replay_checks"][0].update(candidate_answers=1)); self.reject(args)

    def test_postread_and_cleanup_still_required(self):
        args = fixture(); args[0]["cleanup"]["recovery_slice_absent"] = False; self.reject(args)
        args = fixture(); args[1]["preflight_report"]["renderer_sha256"] = "b" * 64; self.reject(args)


if __name__ == "__main__":
    unittest.main()

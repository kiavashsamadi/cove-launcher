import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_resident_sample as checker


def fixture():
    rows = []
    for index in range(3):
        fields = ["0"] * 50
        fields[0] = "S"; fields[11] = str(100 + 25 * index); fields[12] = "10"
        fields[17] = "8"; fields[19] = "10"; fields[21] = str(1000 + 10 * index)
        rows.append(dict(boot="00000000-0000-0000-0000-000000000001",
            uptime_before=str(100 + 30 * index) + ".01 90.00", uptime_after=str(100 + 30 * index) + ".02 90.00",
            stat="42 (resident (app)) " + " ".join(fields), cgroup="8:cpu:/background\n0::/init.scope"))
    return dict(scope="cove-resident-resource-sample-v1", status="read_completed", errors=[],
        root_launched=False, settings_changed=False, apps_launched=False, networking_changed=False,
        cleanup={"sdk_helpers_and_gates_absent": True}, process_identity_verified=True,
        renderer_sha256="a" * 64, protected_before="a" * 64 + "  /private/renderer",
        protected_after="a" * 64 + "  /private/renderer", clock_ticks=250, page_size=4096, samples=rows)


class ResidentSample(unittest.TestCase):
    def reject(self, receipt):
        with self.assertRaises(ValueError): checker.assess(receipt)

    def test_actual_units_and_no_identity_output(self):
        result = checker.assess(fixture())
        self.assertEqual(result["process_cpu_seconds"], 0.2)
        self.assertEqual(result["rss_kib_delta"], 80)
        self.assertEqual(result["background_group_samples"], 3)
        for term in ("resident (app)", "00000000-", "/private/renderer"):
            self.assertNotIn(term, json.dumps(result))
        self.assertFalse(result["speed_improvement_proved"])
        self.assertFalse(result["memory_leak_absence_proved"])

    def test_boot_and_process_reuse(self):
        r = fixture(); r["samples"][1]["boot"] = "00000000-0000-0000-0000-000000000002"; self.reject(r)
        r = fixture(); r["samples"][1]["stat"] = r["samples"][1]["stat"].replace("42 (", "43 ("); self.reject(r)
        r = fixture(); fields = r["samples"][1]["stat"].rsplit(") ", 1); tail=fields[1].split(); tail[19]="11"
        r["samples"][1]["stat"] = fields[0] + ") " + " ".join(tail); self.reject(r)

    def test_units_and_partial_reads(self):
        for key, value in (("clock_ticks", True), ("page_size", 100), ("process_identity_verified", False)):
            r=fixture();r[key]=value;self.reject(r)
        r=fixture();r["samples"].pop();self.reject(r)
        r=fixture();r["samples"][0]["stat"]="42 (bad) S 1 2";self.reject(r)

    def test_bad_timestamps_and_counter_reset(self):
        for value in ("nan 0", "100.02 0 extra", "102.02 0", "99.00 0"):
            r=fixture();r["samples"][0]["uptime_after"]=value;self.reject(r)
        r=fixture();r["samples"][2]["stat"]=r["samples"][0]["stat"];self.reject(r)

    def test_visibility_change_is_not_hidden_claim(self):
        r=fixture();r["samples"][1]["cgroup"]="8:cpu:/foreground"
        result=checker.assess(r)
        self.assertEqual(result["background_group_samples"],2)
        self.assertFalse(result["continuous_hidden_state_proved"])

    def test_preservation_and_cleanup(self):
        for key in ("root_launched", "settings_changed", "apps_launched", "networking_changed"):
            r=fixture();r[key]=True;self.reject(r)
        r=fixture();r["protected_after"]="different";self.reject(r)
        r=fixture();r["cleanup"]={};self.reject(r)

    def test_unknown_fields_and_cgroup_ambiguity(self):
        r=fixture();r["samples"][0]["private_data"]="unexpected";self.reject(r)
        r=fixture();r["samples"][0]["cgroup"]+="\n9:cpu:/foreground";self.reject(r)


if __name__ == "__main__":
    unittest.main()

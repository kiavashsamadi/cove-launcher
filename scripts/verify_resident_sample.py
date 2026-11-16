"""Check a private read-only resource sample; print aggregate counters only.

No TV access. Background cgroup samples do not prove continuous UI visibility,
absence of leaks, physical latency, or a before/after speed improvement.
"""
import argparse
import json
import math
from pathlib import Path
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def uptime(value):
    require(isinstance(value, str) and len(value) <= 128, "Invalid uptime framing")
    fields = value.split()
    require(len(fields) == 2 and all(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", x) for x in fields), "Invalid uptime fields")
    number = float(fields[0])
    require(math.isfinite(number) and 0 < number < 1e12, "Invalid uptime range")
    return number


def process_stat(value):
    require(isinstance(value, str) and len(value) <= 8192, "Invalid process-stat framing")
    match = re.fullmatch(r"([1-9][0-9]*) \(([^\n]*)\) ([RSDZTtXxKWPI]) ([0-9 -]+)", value)
    require(match is not None, "Invalid process-stat fields")
    fields = (match[3] + " " + match[4]).split()
    require(len(fields) >= 22, "Truncated process-stat fields")
    values = [fields[i] for i in (11, 12, 17, 19, 21)]
    require(all(re.fullmatch(r"[0-9]+", x) for x in values), "Invalid resource counter")
    user, system, threads, start, rss = map(int, values)
    require(threads > 0 and start > 0, "Missing process lifetime")
    return dict(identity=(int(match[1]), match[2], start), ticks=user + system, threads=threads, rss_pages=rss)


def cpu_group(value):
    require(isinstance(value, str) and len(value) <= 8192, "Invalid cgroup framing")
    found = []
    for line in value.splitlines():
        match = re.fullmatch(r"[0-9]+:([^:]*):(/[^\n]*)", line)
        require(match is not None, "Invalid cgroup row")
        if "cpu" in match[1].split(","):
            found.append(match[2])
    require(len(found) <= 1, "Ambiguous CPU group")
    return found[0] if found else None


def assess(receipt):
    require(isinstance(receipt, dict) and receipt.get("scope") == "cove-resident-resource-sample-v1"
            and receipt.get("status") == "read_completed" and receipt.get("errors") == [], "Incomplete resource sample")
    require(all(receipt.get(k) is False for k in ("root_launched", "settings_changed", "apps_launched", "networking_changed")),
            "Read-only scope differs")
    require(receipt.get("cleanup") == {"sdk_helpers_and_gates_absent": True}
            and receipt.get("process_identity_verified") is True, "Identity or cleanup incomplete")
    digest = receipt.get("renderer_sha256")
    before = receipt.get("protected_before")
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
            and isinstance(before, str) and before == receipt.get("protected_after")
            and digest + "  " in before, "Protected launcher state differs")
    hz, page = receipt.get("clock_ticks"), receipt.get("page_size")
    require(type(hz) is int and 1 <= hz <= 10000 and type(page) is int
            and page in (4096, 8192, 16384, 32768, 65536), "Native accounting units missing")
    samples = receipt.get("samples")
    require(isinstance(samples, list) and len(samples) == 3, "Three samples required")
    parsed, groups, times, boot = [], [], [], None
    for item in samples:
        require(isinstance(item, dict) and set(item) == {"boot", "uptime_before", "stat", "cgroup", "uptime_after"},
                "Unexpected sample fields")
        require(isinstance(item["boot"], str) and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", item["boot"]),
                "Boot identity missing")
        if boot is None: boot = item["boot"]
        require(item["boot"] == boot, "Boot changed during sample")
        low, high = uptime(item["uptime_before"]), uptime(item["uptime_after"])
        require(0 <= high - low <= 1, "Snapshot read span too large")
        stat = process_stat(item["stat"])
        if parsed:
            require(stat["identity"] == parsed[0]["identity"], "Process identity or start time changed")
            require(stat["ticks"] >= parsed[-1]["ticks"] and 20 <= low - times[-1][1] <= 45,
                    "Counter or sampling interval differs")
        parsed.append(stat); groups.append(cpu_group(item["cgroup"])); times.append((low, high))
    duration = (sum(times[-1]) - sum(times[0])) / 2
    require(55 <= duration <= 75, "Sample duration outside reviewed bound")
    cpu_seconds = (parsed[-1]["ticks"] - parsed[0]["ticks"]) / hz
    rss = [x["rss_pages"] * page // 1024 for x in parsed]
    return dict(resource_sample_verified=True, snapshots=3, duration_seconds=round(duration, 3),
        process_cpu_seconds=round(cpu_seconds, 6), mean_cpu_percent_of_one_core=round(100 * cpu_seconds / duration, 4),
        rss_kib_first=rss[0], rss_kib_last=rss[-1], rss_kib_min=min(rss), rss_kib_max=max(rss), rss_kib_delta=rss[-1]-rss[0],
        threads_first=parsed[0]["threads"], threads_last=parsed[-1]["threads"],
        background_group_samples=sum(x == "/background" for x in groups),
        continuous_hidden_state_proved=False, memory_leak_absence_proved=False, speed_improvement_proved=False,
        physical_latency_measured=False, tv_contacted_by_checker=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    raw = args.receipt.read_bytes()
    require(len(raw) <= 131072, "Receipt exceeds size bound")
    print(json.dumps(assess(json.loads(raw.decode("utf-8-sig"))), indent=2))

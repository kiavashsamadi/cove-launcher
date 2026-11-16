"""Prepare an offline DNS review. Never contacts a TV or starts a resolver."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GROUPS = frozenset({"acr", "advertising", "update_offers", "update_downloads",
                    "reporting", "remote_assistance"})
SHARED_HOSTS = frozenset({"samsung.com", "samsungqbe.com", "samsungcloudsolution.com",
    "samsungcloudsolution.net", "samsungcloud.tv", "samsungcloud.com",
    "samsungcloudcdn.com", "samsungosp.com"})
MAX_BYTES = 65536
MAX_DOMAINS = 256


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def domain(value):
    if not isinstance(value, str) or not value.isascii() or len(value) > 253:
        raise ValueError("Bounded ASCII domain required")
    value = value.lower()
    labels = value.split(".")
    if (len(labels) < 2 or not re.fullmatch(r"[a-z]{2,63}", labels[-1]) or
            any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels)):
        raise ValueError("Domain only: no address, wildcard, URL, port or resolver option")
    if any(host == value or host.endswith("." + value) for host in SHARED_HOSTS):
        raise ValueError("Shared service parent must not be blocked")
    return value


def parse_catalog(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError("Bounded UTF-8 JSON required")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Strict UTF-8 JSON required") from error
    if not isinstance(value, dict) or set(value) != {"schema", "groups"} or type(value["schema"]) is not int or value["schema"] != 1:
        raise ValueError("Exact catalog schema required")
    groups = value["groups"]
    if not isinstance(groups, dict) or not groups or set(groups) - GROUPS:
        raise ValueError("Explicit supported groups required")
    parsed = {}
    count = 0
    for name, entries in groups.items():
        if not isinstance(entries, list) or not entries:
            raise ValueError("Each group needs an explicit nonempty domain list")
        count += len(entries)
        if count > MAX_DOMAINS:
            raise ValueError("Domain count limit exceeded")
        parsed[name] = sorted({domain(x) for x in entries})
    return parsed


def prepare(data, selected):
    groups = parse_catalog(data)
    selected = list(selected)
    if not selected or len(set(selected)) != len(selected) or any(x not in groups for x in selected):
        raise ValueError("Select explicit, distinct catalog groups; no defaults or fallback")
    names = sorted({x for name in selected for x in groups[name]})
    # Isolated test configuration only. A local synthetic upstream must be
    # provided separately. Nothing changes the TV's existing resolver or routing.
    config = ["# Offline review: loopback test harness only; not a deployment file.",
              "port=1053", "listen-address=127.0.0.54", "bind-interfaces",
              "no-resolv", "no-hosts", "cache-size=0", "server=127.0.0.1#9053"]
    for name in names:
        config.extend(["address=/" + name + "/", "local=/" + name + "/"])
    text = "\n".join(config) + "\n"
    report = dict(schema=1, status="prepared_not_installed", tv_contacted=False,
        resolver_started=False, selected_groups=sorted(selected), domains=names,
        catalog_sha256=hashlib.sha256(data).hexdigest(),
        config_sha256=hashlib.sha256(text.encode()).hexdigest(),
        upstream="Loopback synthetic test server only; production upstream undecided",
        qualified_for_deployment=False,
        syntax_validation_is_not_runtime_validation=True,
        deployment_gates=[
            "Review exact domains and suffix effects; syntax validation does not prove safety",
            "Choose an explicit trusted upstream and continuously available resolver host",
            "Test A, AAAA and other query types against blocked names and subdomains",
            "Test permitted names, lookalikes, UDP/TCP, timeouts and resolver loss",
            "Verify native DNS settings, IPv4/IPv6 alternate paths and independent recovery",
            "Record all existing rules; any approved hooks must have a scoped inverse",
            "Validate clock synchronization, local control and required TV functions",
            "Review exact deployment and recovery before changes; test restart separately"],
        limits=["Candidate domains are not evidence of collection by a particular device",
                "DNS filtering does not cover unknown hosts, cached or hard-coded addresses, alternate DNS or encrypted resolver bypass",
                "Updates, reporting and remote support require separate compatibility decisions",
                "No service disable, settings write, firewall rule or startup installation is generated"])
    return text, report


def write_review(catalog, selected, output, private_root=None):
    """Create a new private review; never replace a previous reviewed policy."""
    with catalog.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    text, report = prepare(data, selected)  # Reject invalid input before any write.
    private_root = (ROOT / ".local" if private_root is None else private_root).resolve()
    requested = Path(output).absolute()
    # Check the un-resolved path too, so an alias inside .local cannot redirect
    # output through an existing link. No symlink component is permitted.
    if any(p.is_symlink() for p in (requested, *requested.parents)):
        raise ValueError("Output symlinks are not permitted")
    output = requested.resolve()
    if output == private_root or not output.is_relative_to(private_root):
        raise ValueError("Use a new directory below the checkout's .local directory")
    if output.exists():
        raise ValueError("Review exists; use a new directory, never overwrite a reviewed policy")
    output.mkdir(parents=True, exist_ok=False)
    (output / "dnsmasq-lab.conf").write_text(text, encoding="utf-8", newline="\n")
    (output / "review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    # Written last: partial output is not a complete review if interrupted.
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (output / "dnsmasq-lab.conf", output / "review.json")}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--groups", nargs="+", choices=sorted(GROUPS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = write_review(args.catalog, args.groups, args.output)
    print(json.dumps({key: report[key] for key in
        ("status", "tv_contacted", "resolver_started", "qualified_for_deployment", "selected_groups")}, indent=2))


if __name__ == "__main__":
    main()

"""Offline transaction model, not a TV executor or a deployable DNS policy.

The in-memory backend makes interruption, ownership and concurrent-change
semantics testable. Native atomicity and an independent recovery executor still
need qualification. No network, filesystem or subprocess operations occur here.
"""
from dataclasses import dataclass, field


class Conflict(RuntimeError):
    """Refuse to overwrite state that neither we nor the snapshot own."""


class Interrupted(RuntimeError):
    """Injected interruption after an atomic model operation."""


@dataclass
class MemoryBackend:
    dns: str = "original-dns"
    rules: dict = field(default_factory=lambda: {"vendor": "vendor-rule"})
    resolver: bool = False
    snapshot: dict | None = None
    events: list = field(default_factory=list)
    crash_after: int | None = None

    def event(self, name):
        self.events.append(name)
        if self.crash_after == len(self.events):
            raise Interrupted(name)


@dataclass(frozen=True)
class Plan:
    token: str = "synthetic-trial"
    candidate_dns: str = "candidate-loopback"
    rule4: str = "synthetic-v4-redirection"
    rule6: str = "synthetic-v6-redirection"

    @property
    def rules(self):
        return {self.token + ":v4": self.rule4, self.token + ":v6": self.rule6}


def prepare(backend, plan):
    if backend.snapshot is not None or backend.resolver:
        raise Conflict("An active transaction must be reconciled first")
    if backend.dns == plan.candidate_dns or any(k in backend.rules for k in plan.rules):
        raise Conflict("Candidate state already exists")
    # This single assignment models a durable, authenticated, atomic journal.
    # A real implementation must establish those properties independently.
    backend.snapshot = {
        "token": plan.token, "dns": backend.dns, "rules": dict(plan.rules),
        "candidate": plan.candidate_dns,
    }
    backend.event("snapshot-committed")


def validate_snapshot(backend, plan):
    snap = backend.snapshot
    if (not isinstance(snap, dict) or set(snap) != {"token", "dns", "rules", "candidate"}
            or snap["token"] != plan.token or snap["rules"] != plan.rules
            or snap["candidate"] != plan.candidate_dns
            or not isinstance(snap["dns"], str) or not snap["dns"]
            or snap["dns"] == plan.candidate_dns):
        raise Conflict("Missing or mismatched recovery journal")
    return snap


def activate(backend, plan):
    snap = validate_snapshot(backend, plan)
    if backend.dns != snap["dns"] or any(k in backend.rules for k in plan.rules):
        raise Conflict("Activation baseline changed")
    if backend.resolver:
        raise Conflict("Unexpected resolver already running")
    # Each event represents one completed, read-back-verified model operation.
    backend.resolver = True
    backend.event("resolver-ready")
    for key, value in plan.rules.items():
        if backend.dns != snap["dns"] or key in backend.rules:
            raise Conflict("Activation state changed between operations")
        backend.rules[key] = value
        backend.event("rule-added:" + key.rsplit(":", 1)[1])
    if backend.dns != snap["dns"] or any(backend.rules.get(k) != v for k, v in plan.rules.items()):
        raise Conflict("Activation baseline changed before DNS switch")
    backend.dns = plan.candidate_dns
    backend.event("dns-switched")


def recover(backend, plan):
    snap = validate_snapshot(backend, plan)
    # Validate every owned target before beginning the inverse. In a native
    # executor each individual mutation also needs an atomic compare-and-set.
    if backend.dns not in (snap["dns"], plan.candidate_dns):
        raise Conflict("DNS changed independently; resolver retained")
    for key, value in plan.rules.items():
        if key in backend.rules and backend.rules[key] != value:
            raise Conflict("Owned rule changed independently; resolver retained")
    # Remove interception before restoring native DNS, then release the worker.
    # This is an explicit availability-first recovery to the recorded policy;
    # it is not a promise that filtering continues during failure recovery.
    for key in reversed(tuple(plan.rules)):
        if key in backend.rules:
            if backend.rules[key] != plan.rules[key]:
                raise Conflict("Rule changed during recovery; resolver retained")
            del backend.rules[key]
            backend.event("rule-removed:" + key.rsplit(":", 1)[1])
    if backend.dns == plan.candidate_dns:
        backend.dns = snap["dns"]
        backend.event("dns-restored")
    if backend.dns != snap["dns"] or any(k in backend.rules for k in plan.rules):
        raise Conflict("Recovery baseline changed before resolver stop")
    if backend.resolver:
        backend.resolver = False
        backend.event("resolver-stopped")
    backend.event("recovery-verified")
    # Keep the immutable snapshot for repeated recovery and auditing. A native
    # cleanup phase must separately verify no remaining clients depend on it.


def exercise():
    """Exhaust every modeled interruption, returning only aggregate counts."""
    plan = Plan()
    runs = 0
    for cut in range(1, 6):
        b = MemoryBackend(crash_after=cut)
        try:
            prepare(b, plan)
            activate(b, plan)
        except Interrupted:
            pass
        b.crash_after = None
        recover(b, plan)
        assert b.dns == "original-dns" and b.rules == {"vendor": "vendor-rule"}
        assert not b.resolver
        runs += 1
    for cut in range(1, 6):
        b = MemoryBackend()
        prepare(b, plan)
        activate(b, plan)
        b.crash_after = len(b.events) + cut
        try:
            recover(b, plan)
        except Interrupted:
            pass
        b.crash_after = None
        recover(b, plan)
        assert b.dns == "original-dns" and b.rules == {"vendor": "vendor-rule"}
        assert not b.resolver
        runs += 1
    return {"modeled_interruptions_recovered": runs, "tv_contacted": False,
            "native_transaction_qualified": False, "production_dns_qualified": False}


if __name__ == "__main__":
    import json
    print(json.dumps(exercise(), indent=2))

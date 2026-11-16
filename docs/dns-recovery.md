# Isolated DNS recovery

A transient service managed by the TV's existing system manager passed the
isolated lifecycle tests below. This is stronger evidence than a supervisor's
own timeout: the manager removed the trial resolver even after its launch client
was killed or the resolver was frozen. **A permanent on-TV resolver is still
unqualified.** Privilege minimization and recovery of real DNS routing remain
separate requirements.

## Native evidence

The tested manager reports systemd 244. Each trial used a unique transient
service with an independent three-second runtime limit, bounded startup/stop,
control-group termination, no restart and collection after success or failure.
No unit was enabled for boot. Native properties, process identities, control
groups and loopback sockets were checked before injecting a fault. The design
uses the documented [service lifetime](https://github.com/systemd/systemd/blob/v244/man/systemd.service.xml),
[group termination](https://github.com/systemd/systemd/blob/v244/man/systemd.kill.xml)
and [transient service](https://github.com/systemd/systemd/blob/v244/man/systemd-run.xml)
mechanisms; the device tests establish which behaviors worked on this firmware.

| Isolated case | Observed result |
| --- | --- |
| Manager deadline | Resolver removed without a controller stop |
| Frozen resolver | Manager removed the stopped process at its deadline |
| Launch-client loss | Resolver survived loss of the waiting launch client, then expired independently |
| Parent exits through a normal-exit handler | Manager removed the remaining resolver child before the runtime limit |
| Parent killed | Remaining resolver child removed before the runtime limit |
| Resolver killed | Process, service, group and listeners removed |
| Fresh launch after crash | DNS responses succeeded; scoped stop succeeded |
| Invalid resolver option | Startup refused; no service or listener remained |
| Explicit inverse | Only the verified owned service stopped; resources released |
| Functional DNS run | Synthetic response and upstream-outage/recovery checks passed; scoped stop succeeded |

The second batch recorded 239 DNS response assertions, including readiness,
exact/suffix/lookalike names, A/AAAA/TXT, IPv4/IPv6 loopback, UDP/TCP and restart.
Denied queries did not reach the synthetic upstream. No external DNS queries
were sent by the trial and no real TV traffic was redirected. Independent
cleanup reads found no trial service, listener, control group or staged payload.
Native DNS, firewall rules, system binaries and their capabilities were preserved.

The resolver ran with an unprivileged numeric identity, no-new-privileges and
empty effective, permitted, inheritable, ambient and bounding capability sets.
However, the firmware supplied additional supplementary groups. Empty and
explicit service group settings did not minimize the observed group list.
A restricted managed startup wrapper was refused before a resolver started;
the precise refusal cause was not established. No executable-signature check,
capability attribute or security policy was weakened to make it run.

The successful lifecycle matrix therefore records **supplementary-group
minimization as false**. Its temporary workers were restricted to synthetic
loopback queries and had no file-writing configuration. Those results do not
approve those groups for an unattended service. The earlier parent-death-signal
failure remains a failure of that separate design; it is not rewritten as a pass.

## Routing recovery design

Stopping a resolver is insufficient once clients depend on it. A later design
needs a durable private baseline and recovery execution that survives loss of
the launch client **and** the resolver. The candidate recovery sequence is:

1. Verify the journal, transaction identity and exact owned rules against current state.
2. Remove only owned interception rules for both address families.
3. Restore the recorded native DNS state if it still matches this transaction's candidate.
4. Verify that no owned route depends on the resolver, then stop it.
5. Verify cleanup and retain the recovery record for an idempotent retry.

This is an availability-first return to the recorded network policy; filtering
would cease during recovery. It must be an explicit deployment choice. A policy
that instead blocks outbound access during failure requires a different,
separately reviewed design. Never silently choose an external fallback resolver.

[`simulate_dns_recovery.py`](../scripts/simulate_dns_recovery.py) models these
operations in memory. Tests cover all ten modeled activation/recovery
interruption points, repeated recovery, a dead worker, missing journals,
conflicts before and between operations, and preservation of unrelated rules.
On conflict the model refuses to overwrite another change or stop a resolver
that may still be needed. A real implementation needs native atomic conditional
writes or equivalent serialization; Python assignments do not establish that.
Journal durability/authenticity and a separately supervised recovery executor
are assumptions of the model, not completed native features.

```text
python scripts/simulate_dns_recovery.py
python scripts/verify_dns_manager.py --deadline /absolute/private/deadline-result.json --recovery /absolute/private/recovery-result.json
```

These tools do not contact a TV. The receipt checker requires all ten cases,
exact response coverage, manager controls and independent cleanup evidence. It
prints aggregate results only and keeps production/routing qualification false.
It checks consistency, not receipt authenticity, freshness or arbitrary logs.
Keep native payloads and raw receipts private.

## Remaining qualification

- Establish a supported, sufficiently restricted worker identity without weakening platform security.
- Implement and test the independent recovery executor and its durable journal.
- Qualify actual DNS-setting and owned-rule inverses, both address families and concurrent native changes.
- Choose the failure policy and real upstream explicitly; test local control and required native functions.
- Test standby, cold boot, full power loss and interruption of real control connectivity separately.

The launch-client test did not disconnect the PC or network, and no reboot was
part of this trial. The manager itself was never stopped. Passing process
containment does not establish recovery from manager/kernel failure or power
loss. A reliable external LAN resolver remains an alternative; neither approach
alone proves that every telemetry path is blocked.

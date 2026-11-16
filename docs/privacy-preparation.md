# Offline privacy review tools

The scripts here prepare and audit changes against private registry snapshots.
They do not connect to a TV or authorize deployment. Applied measures and
remaining gaps are described in [privacy status](privacy-status.md).

## Prepare a review

```text
python scripts/prepare_privacy.py --snapshot /absolute/local/snapshot.db --receipt /absolute/local/receipt.json --output /absolute/checkout/.local/new-review
```

The input must be a consistent, receipt-verified SQLite backup. The receipt needs
a matching `databases` item containing `file`, `source`, `bytes`, `sha256` and
`integrity:["ok"]`. Private output belongs in a new directory below `.local/`.

The tool checks hash, size, integrity and schema, then inventories explicit app
IDs. Candidate lists are triage inputs, not proof that an app is tracking or safe
to disable. Generated drafts are alternatives, not a batch to apply together.
Missing apps, shared protected packages, unexpected encodings, triggers and
state drift require review.

For a package catalog comparison, `compare_package_inventory.py` accepts private
JSON containing `catalog` (package IDs), `packages` (rows with `package`) and
`apps` (rows with `app_id`, `package` and native text `disable` values). It reports
absent packages, missing app rows and mixed sibling flags separately. Similar
display names are never used to infer identity. This is a global-registry
comparison, not a runtime or per-user verification; keep its inputs private.

`audit_privacy_drafts.py` tests isolation, inverse operations and failure cases on
disposable copies. Passing these tests proves neither native service behavior nor
network privacy. `verify_review_packet.py` checks private archive paths, sizes and
hashes without extracting or executing their contents.

## Native operation boundaries

Native app deactivation can terminate the target process before updating its
registration. Re-enabling a flag does not restore interrupted work. A process
snapshot is not an atomic guarantee that the app cannot launch immediately after
the check. Account for this side effect when qualifying each target, particularly
app synchronization and other components that can start installation work.

The offline batch policy requires `apply_is_terminal(stage)` before advancing or
issuing an inverse. Its private adapter must correlate completion with the exact
native request and establish that no late write can follow. CLI timeout, client
termination, request acceptance and a single unchanged registry read do not
establish this. If completion is unknown, the policy reports recovery required;
it can still restore earlier stages with proven completion. This contract and
its delayed-request tests do not implement native request cancellation or make
an unqualified TV operation safe.

[`native_app_completion.py`](../scripts/native_app_completion.py) validates the
matching app-specific start and successful end callbacks from a captured native
command, together with its natural successful exit. It rejects incomplete,
mixed-request, timed-out and failed captures. In the inspected implementation,
the successful end callback follows the registration write. A private adapter
must still bind the capture to its owned process, exact native tool build and
reviewed operation; this offline parser cannot authenticate a receipt or qualify
a new target. Unknown completion remains an unresolved outcome, not permission
to race an inverse against a late write.

## Verify operational receipts offline

```text
python scripts/verify_privacy_receipts.py --apps /absolute/local/app-check.json --pisa /absolute/local/pisa-check.json
```

This checks the exact nine global flags and underlying app rows, process samples,
four PISA/adagent activation units, marker identity, Home/startup preservation
and diagnostic cleanup. Missing or contradictory evidence fails. It neither
contacts the TV nor claims a fresh restart or complete telemetry prevention.

For a separate read-only automatic-update policy receipt:

```sh
python scripts/verify_update_policy.py --receipt /absolute/local/update-policy-read.json
```

This requires all four typed policy values to be off, the three inspected
pending-update values to be zero, known upgrade markers to be absent, and clean
diagnostic completion. It rejects missing keys, duplicate values, type mismatches
and incomplete reads. It does not establish receipt freshness, restart
persistence or protection against every update path. Keep raw receipts private;
the command prints only its bounded assessment.

For isolated DNS response and recovery receipts, use
[`verify_dns_trial.py`](../scripts/verify_dns_trial.py) as described in the
[network review](network-review.md). It distinguishes a safely recovered failure
from successful automatic cleanup. Valid evidence is not deployment approval;
raw receipts, operational payloads and firmware binaries stay outside Git.

The [stronger recovery design](dns-recovery.md) adds [a confinement/inverse receipt checker](../scripts/verify_dns_confinement.py),
manager evidence checks and an in-memory transaction model. They distinguish
restricted-worker, isolated native routing and independent deadline-recovery passes from still-unqualified
live-network deployment. The [controller-loss/replay checker](../scripts/verify_dns_controller_loss.py)
also checks automatic cleanup, backup deadlines, retained-connection limits and
probe-versus-background traffic accounting. It never promotes a narrow replay
to all-app compatibility. None performs or authorizes deployment.

`socket_metadata.py` validates two fixed selected-process socket samples and
decodes full IPv4/IPv6 endpoints from little-endian Linux proc records. It rejects
truncated addresses, missing protocol coverage, unknown owners, changed process
identity and output overflows. Disappeared processes before name lookup are
counted explicitly and never used to prove process absence. The parser does not capture payload contents or measure transmission rates.
Keep endpoint and process receipts private; only synthetic fixtures belong in Git.

The metadata format follows the [kernel proc TCP documentation](https://kernel.org/doc/html/v5.19/networking/proc_net_tcp.html)
and [Linux socket inode mapping](https://www.man7.org/linux/man-pages/man5/proc_pid_fd.5.html).

## Before a permanent change

For DNS candidates, use the [network review workflow](network-review.md). It
creates an isolated lab configuration and an explicit qualification checklist;
it does not configure the TV, router, firewall or a DNS service.

Identify the exact firmware, app/service, callers and activation paths. Preserve
the current state and specify a narrow inverse before changing it. Prefer native
app-management operations over raw registry edits. Compare unrelated registries,
saved presets and Home/startup after execution; verify required functionality and
restart persistence when relevant.

Keep original files, snapshots, signed plans and raw evidence outside Git. New
targets require authorization and an exact scoped recovery plan. Do not infer safety from a package name,
privilege list, empty dependency table or a missing process in one snapshot.

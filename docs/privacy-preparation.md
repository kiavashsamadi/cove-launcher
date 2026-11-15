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

`audit_privacy_drafts.py` tests isolation, inverse operations and failure cases on
disposable copies. Passing these tests proves neither native service behavior nor
network privacy. `verify_review_packet.py` checks private archive paths, sizes and
hashes without extracting or executing their contents.

## Verify operational receipts offline

```text
python scripts/verify_privacy_receipts.py --apps /absolute/local/app-check.json --pisa /absolute/local/pisa-check.json
```

This checks the exact nine global flags and underlying app rows, process samples,
four PISA/adagent activation units, marker identity, Home/startup preservation
and diagnostic cleanup. Missing or contradictory evidence fails. It neither
contacts the TV nor claims a fresh restart or complete telemetry prevention.

`socket_metadata.py` validates two fixed selected-process socket samples and
decodes full IPv4/IPv6 endpoints from little-endian Linux proc records. It rejects
truncated addresses, missing protocol coverage, unknown owners, changed process
identity and output overflows. Disappeared processes before name lookup are
counted explicitly and never used to prove process absence. The parser does not capture payload contents or measure transmission rates.
Keep endpoint and process receipts private; only synthetic fixtures belong in Git.

The metadata format follows the [kernel proc TCP documentation](https://kernel.org/doc/html/v5.19/networking/proc_net_tcp.html)
and [Linux socket inode mapping](https://www.man7.org/linux/man-pages/man5/proc_pid_fd.5.html).

## Before a permanent change

Identify the exact firmware, app/service, callers and activation paths. Preserve
the current state and specify a narrow inverse before changing it. Prefer native
app-management operations over raw registry edits. Compare unrelated registries,
saved presets and Home/startup after execution; verify required functionality and
restart persistence when relevant.

Keep original files, snapshots, signed plans and raw evidence outside Git. New
targets require authorization and an exact scoped recovery plan. Do not infer safety from a package name,
privilege list, empty dependency table or a missing process in one snapshot.

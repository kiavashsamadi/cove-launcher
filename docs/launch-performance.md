# Launch and return behavior

Cove retains its native scene between uses and hides it when returning to HDMI.
Explicit Exit releases it. The TV may reclaim a hidden app; a reclaimed process
or restart requires a cold start. No boot preloader or keep-alive daemon is added.

Artwork is local. Picture and input reads run off the UI thread. The first warm
frame uses a prepared input hint, while current-input claims and picture controls
wait for fresh observations. The outgoing frame stays unchanged during Back.

Only an explicit Home request raises a cached window. Native activation may need
up to two additional 80 ms UI turns before resume acknowledgement. One
lifetime-owned timer stops on acknowledgement, return or backgrounding; it is
disposed at termination, not from its own callback.

Ordinary hidden state stops periodic polling and animation. A native source-list
notification can update the cached input/audio inventory while hidden, without
reading picture settings or raising the window. Visible inventory refresh also
runs at a 500 ms fallback interval. Requests coalesce into one reader. A different Cove card may
finish one bounded brightness continuation after the native signal settles.
It never raises the hidden window or keeps polling indefinitely.

Back derives its destination from the freshly read current HDMI source, not the
highlighted card, and does not call picture setters. Source activation can pause
Cove before its worker returns; that pause completes the visibility handoff.
Unrelated app-control messages and late worker replies cannot restart an old
foreground session. A rejected return has a viewer-launch fallback.

Host lifecycle tests include repeated Home/Back, asynchronous source pauses,
reentrant native resume, stale replies, Settings, caption continuity and hidden
work. These do not establish physical key-to-frame latency or long-run memory.
No percentage speed improvement or universal instant-open guarantee is claimed.
See [validation](remaining-validation.md).

## Resident resource sample

A bounded read-only native sample recorded one CPU-accounting tick (4 ms) over
60.89 seconds, approximately 0.0066% of one CPU core. Resident memory was 93,960
KiB (about 91.8 MiB) at all three snapshots, with 32 threads. The process was in
the background CPU group at each snapshot; its identity, start time and boot
identity stayed stable. Launcher routing and the installed renderer matched
before and after, and the temporary diagnostic helpers were removed.

This is one interval on the tested build, not a speed comparison, continuous
visibility trace or long-run leak test. RSS is an approximate resident-memory
counter and includes shared pages; it is not private memory. CPU tick and page
sizes were read from the native system rather than assumed. See the kernel's
[process accounting documentation](https://docs.kernel.org/filesystems/proc.html).

The offline [resource checker](../scripts/verify_resident_sample.py) validates
the private receipt and prints aggregates without process, boot or device
identifiers:

```sh
python scripts/verify_resident_sample.py /absolute/private/resource-result.json
```

Its regressions cover process reuse, counter resets, accounting units, malformed
reads, visibility-group changes, preservation and cleanup. It never contacts a
TV and does not qualify an optimization or a background-service disable.

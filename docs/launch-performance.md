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

Ordinary hidden state stops polling and animation. A different Cove card may
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

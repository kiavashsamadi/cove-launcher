# Brightness and shared profiles

Cove changes brightness only. It does not switch the native picture mode or
alter Game Mode, HDR configuration, contrast, color, audio or source labels.
The control is available on active HDMI inputs when Samsung reports brightness
as adjustable and a coherent picture context is available.

## Bright and Dim

Bright defaults to 50 and Dim to 0. Select either, then open Brightness to change
that shared level. Changes apply live and update the memory only after successful
native readback. Back or Select closes the panel and keeps the value.

One pair is shared across HDMI inputs, native modes and SDR/HDR. Equal numbers
do not promise equal perceived luminance. A profile is selected only when an
explicit choice matches the observed brightness; numerical equality alone does
not select it. Without an active profile, adjusting brightness leaves both
memories unchanged. Equal Bright and Dim numbers retain the explicit choice.

The toolbar controls the current source. Hovering another input previews it;
moving to the toolbar returns the hero to the source being controlled. Unsettled
picture data appears as an ellipsis, never a fabricated zero. A stale or mixed
observation cannot authorize a write.

## Input changes

An explicitly selected profile can follow a different Cove input card. One
serialized continuation waits up to 6.5 seconds, requiring at least 3.2 seconds
after activation, a stable context for one second, and fresh coherent native
source, signal and active-mode observations. It makes at most one brightness
write. An uncertain write is not retried.

Home can observe a pending handoff without cancelling it. Back, Settings, Exit,
a newer card or a new brightness action cancels unsent work. The continuation
never raises Cove or adds an ongoing hidden poll. Native calls cannot be made
atomic with an external HDMI/CEC change or forcibly interrupted safely.

Manual brightness drift in the same context is confirmed across observations
before releasing automatic following. An input change is not itself a manual
override. External CEC changes and later HDR transitions do not trigger an
automatic profile write. If a destination never becomes ready, it is left alone;
select a profile after it settles.

## Samsung scope

**Current source / All sources** changes Samsung's Apply Picture Settings option
only on explicit selection when the platform permits it. An unavailable option,
including the tested Game Mode restriction, becomes a read-only label.
Brightness and profiles remain separate from that capability.

Cove does not change scope when recalling a profile. All sources may propagate
picture values according to Samsung's implementation; exact cross-source effects
are not comprehensively measured. Returning to Current source does not undo
previously copied values.

## Writes, storage and recovery

Each action checks source, mode, scope, brightness, range, availability and
freshness before writing and verifies the result. Rapid arrows replace one
pending target instead of queueing every step. Writes are serialized with a
minimum 120 ms interval; failures and a three-second deadline stop pending edits.
No direct Samsung database editing is used by the renderer.

Shared numbers use a versioned application-data file. Saves are coalesced,
flushed and atomically replaced. Invalid files are preserved; errors are reported.
Legacy per-context data is retained, and ambiguous migration is refused.

Renderer recovery preserves profile files and intentional brightness/scope edits.
Do not restore an entire old picture database to undo one slider adjustment.
See [validation](remaining-validation.md) for tested coverage and remaining limits.

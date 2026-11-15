# Validation

Host checks compile the production control and lifecycle code with simulated
platform interfaces. Coverage includes stable observations, brightness-only
writes, shared memory, native scope restrictions, source settling, cancellation,
reentrant activation, repeated Back, Settings and persistence error handling.
Browser checks cover keyboard/pointer navigation, modal focus, missing inputs,
reduced motion and smaller viewports.

The current production build passed native Home/current-input-card/Back cycles,
direct Settings opening and return, and Bright/Dim following in both directions
between an HDR playback input and a Game Mode input. The test restored the
original brightness levels and profile-file bytes. All saved tuning and scope
values matched the immediate backup; the only table difference was the native
active-mode selector entering Game Mode on console activation.

Installation preserved all six picture tables. Existing routing, nine app-disable
flags and PISA/adagent startup blocks passed verification. Temporary diagnostic
sessions verify cleanup; private receipts, raw databases, endpoint data and
diagnostic traces are not distributed.

## Limits

- Host and browser passes cannot establish physical picture/sound quality.
- A bounded native check is not proof against every remote/CEC timing race.
- Full All sources propagation and every SDR/HDR transition are not qualified.
- Shared profile persistence across a full restart, accessibility speech,
  full AC removal, future firmware and long-run memory need separate coverage.
- Complete telemetry prevention and numerical speed improvements are not claimed.

A guard stop is treated as untested, not as a pass or evidence that the launcher
failed. Physical picture, sound and perceived motion require a separate
visual/audio check. No absence-of-all-bugs guarantee is implied.

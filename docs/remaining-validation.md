# Validation

[The regression suite and feature matrix](regression-testing.md) cover shipped
behaviors and run in public CI. Host checks compile the production control and lifecycle code with simulated
platform interfaces. Coverage includes stable observations, brightness-only
writes, shared memory, native scope restrictions, source settling, cancellation,
reentrant activation, repeated Back, Settings and persistence error handling.
Browser checks cover keyboard/pointer navigation, modal focus, missing inputs,
reduced motion and smaller viewports.

Brightness/profile logic previously passed native following in both directions
between playback and Game Mode inputs, with saved values restored. The audio/
hotplug update keeps that logic and adds independent inventory handling. Native
Home/current-input-card/Back cycles, the general Settings cog and the audio
shortcut passed on the updated build. A private screen capture confirmed the
Sound category; both menus stayed open and the original viewer returned. These
checks and physical limits are distinct from the prior signal/brightness checks;
the offline regressions exercise the combined production code on every change.

Installation preserved all six picture tables. Existing routing, nine app-disable
flags and PISA/adagent startup blocks passed verification. Temporary diagnostic
sessions verify cleanup; private receipts, raw databases, endpoint data and
diagnostic traces are not distributed.

The four automatic-update policies remained off after a confirmed new boot.
Fresh reads also verified the existing component controls, routing, renderer
and all six picture-setting tables. Physical navigation, picture and sound were
confirmed separately after that restart.

The separate web advertising player's native disable/enable round trip and
controlled validation-failure recovery passed. Its subsequent single-flag
deployment passed full global, owner, web-app and picture-table comparisons,
with launcher routing, update controls, networking and diagnostic cleanup
preserved. A subsequent confirmed cold boot preserved the new flag, the existing
controls and all six picture tables, compared with a fresh baseline that includes
intentional picture changes. Navigation, picture and sound were confirmed
separately after startup.
The native application-information API independently reports the web player as
disabled and the launcher carrier as enabled for the same owner context, both
before and after that reboot. This
checks the metadata view, not every possible activation path; neither app was
launched or reloaded for the query.

## Limits

- Host and browser passes cannot establish physical picture/sound quality.
- A native capture confirmed that an unplugged HDMI port was absent, with other
  inputs still usable. Cable reconnection and event timing while open or hidden
  remain covered by simulation rather than physical validation.
- A bounded native check is not proof against every remote/CEC timing race.
- Full All sources propagation and every SDR/HDR transition are not qualified.
- Shared profile persistence across a full restart, accessibility speech,
  full AC removal, future firmware and long-run memory need separate coverage.
- Complete telemetry prevention and numerical speed improvements are not claimed.
- DNS filtering remains a lab candidate. Complete diagnostic-agent loss and an
  interrupted primary inverse recovered with independent backup and automatic
  native cleanup. Native libc TCP reconnect and NSS IPv4/IPv6 fallback passed.
  An isolated client-cgroup variant also passed complete-controller-loss recovery
  while nonmember DNS remained unaffected.
  A separate live-network owned-client trial verified the same combined fault,
  with independent cleanup reconciliation and later host-state readback.
  A raw retained TCP connection still reset. A longer passive sample observed
  two background questions, but a separate replay sample observed none and
  therefore adds no background-replay coverage. Ordinary-app compatibility and persistent
  startup remain unqualified. See [DNS recovery](dns-recovery.md).
  An offline boot-recovery model tests interruptions and ownership conflicts;
  its atomic durable journal and compare-and-set are assumptions, not native
  persistence or power-loss qualification.

A guard stop is treated as untested, not as a pass or evidence that the launcher
failed. Physical picture, sound and perceived motion require a separate
visual/audio check. No absence-of-all-bugs guarantee is implied.

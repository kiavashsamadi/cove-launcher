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
  A raw retained TCP connection still reset; limited replay observed no
  background-app queries. Ordinary-app/live-network compatibility and persistent
  startup remain unqualified. See [DNS recovery](dns-recovery.md).

A guard stop is treated as untested, not as a pass or evidence that the launcher
failed. Physical picture, sound and perceived motion require a separate
visual/audio check. No absence-of-all-bugs guarantee is implied.

# Lifecycle integration

An app-control request is not proof that the physical Home button was pressed.
Cove classifies the operation and supported entry marker, rejects unrelated
requests during handoff, and uses foreground generations to discard stale work.
See Samsung's [AppControl API](https://samsung.github.io/TizenFX/API9/api/Tizen.Applications.AppControl.html)
and [received-control API](https://samsung.github.io/TizenFX/API9/api/Tizen.Applications.ReceivedAppControl.html).

Native source activation can pause the app before the source call returns.
That pause must complete hiding without waiting for an invalidated UI callback.
Accepted source activation does not launch the viewer a second time merely
because readback is still settling. Home can observe the bounded brightness
handoff; a newer control cancels unsent work.

Warm artwork is prepared while hidden or before Show. It is only a hint: fresh
source and picture observations gate controls. Settings keeps its caller alive,
but Cove must not raise over it in an incidental resume callback.

Home activation uses one reusable native timer. Synchronous resume acknowledgement
stops the timer; final disposal happens at app termination. A regression test
exercises reentrant resume from inside Activate. Samsung's
[Timer implementation](https://github.com/Samsung/TizenFX/blob/main/src/Tizen.NUI/src/public/Utility/Timer.cs)
explains the native callback lifetime, but does not by itself prove a device bug's
cause. Host tests simulate framework scheduling; native checks remain necessary.

The renderer adds no persistent root service, hidden keep-alive watchdog or
continuous background monitor. See [launch behavior](launch-performance.md)
and [validation limits](remaining-validation.md).

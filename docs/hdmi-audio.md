# HDMI inputs and sound systems

Cove shows connected video inputs. A sleeping device stays visible while the TV
reports it connected. Names come from the TV; an unnamed device is HDMI plus its
port number. An unplug ends name retention so a new device cannot inherit an old
console name.

The source list is an inventory, not a required four-row table. A valid report
may contain zero to four HDMI ports. Missing or disconnected ports disappear;
focus moves to a remaining card or the toolbar. Malformed information for one
port does not disable unrelated valid ports. A completely unreadable report
retains visual hints, but every input selection checks native connectivity again.
It does not leave an indefinite checking-inputs lock.

Native source-list events refresh the cache even while Cove is hidden. While
visible, a 500 ms fallback refresh catches missed events. Reads coalesce rather
than accumulating. The newest cached list is used before showing a warm window;
a fresh read follows. This is prompt response to Samsung's reported state, not
a guarantee of zero latency from the physical connector. If the TV reclaims the
app, the next launch reads the inventory anew.

## Audio control

A device classified by the TV as an HDMI sound system appears in the toolbar,
immediately left of Brightness. Its label shows the reported device name and
physical HDMI port. eARC is added only when the native receiver-capability read
positively supports it. That label does not establish the active audio output,
audio format or negotiated connection. Unknown capability is omitted.

Select opens Samsung's Sound settings. It never switches the picture to the
sound system's HDMI port or changes sound settings. Disconnecting the endpoint
removes the control; focus moves to Brightness if needed. Video cards remain
separate. With multiple audio endpoints, the control becomes a generic Sound
settings shortcut rather than claiming one is the active output.

## Coverage

Host tests exercise partial/empty/malformed reports, unplug/replug identity,
sleeping devices, audio classification, notification bursts, hidden updates,
warm reopening, focus recovery and a disconnect immediately before selection.
Browser tests cover the control layout, Sound action, uncertain eARC labels,
remote navigation and removal of the focused control.

Physical cable removal and reconnection cannot be simulated by ordinary source
selection. That hardware event remains distinct from host simulation and native
API registration/navigation checks. No service restart, CEC power command or
hardware-port reconfiguration is used to imitate an unplug.

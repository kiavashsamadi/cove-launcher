# Design

A dark cinematic canvas, one large device graphic and a compact input dock keep
the main action clear. The interface has no wordmark, decorative frame around
the hero, persistent instructions or diagnostic text.

Focus previews a device; **Current input** identifies what is actually playing.
Brightness, Bright/Dim and Settings use the current source. Moving back to the
dock restores the last card preview. Port numbers stay on cards.

TV-reported names choose labels and artwork. Unknown devices receive a generic
HDMI label rather than a guessed console name. Unplugged inputs disappear;
connected sleeping devices can remain. Failed inventory reads retain previous
cards as temporary hints; selecting one performs a fresh native check rather
than waiting indefinitely. A bad report for one port does not disable the other
valid inputs. See [HDMI and audio behavior](hdmi-audio.md).

A detected HDMI sound system appears immediately left of Brightness, with its
reported name and physical port. It opens the native Sound category. It is not
a video-input card or a claim about the currently active audio output.

The cog opens native Settings directly. Back preserves the outgoing frame until
the HDMI handoff; hidden preparation resets focus for the next Home opening.
Remote input does not wait for decorative transitions.

Brightness applies live, and the panel title identifies a shared profile when
editing one. Samsung scope remains an explicit separate control; unavailable
scope appears as a label. See [brightness](brightness.md).

Local artwork and native NUI views avoid a browser engine, downloaded fonts,
runtime blur and continuous animation. Brand marks identify device families;
their attribution and notices are retained in the shared artwork directory.

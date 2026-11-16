# Launcher gallery

The first image is a native 1920 × 1080 capture from the development TV. The
remaining images are offline browser previews with sample input names and
connections. Screenshots show appearance; they do not establish transition timing
or physical picture and sound.

## On the TV

![Cove on the TV with detected audio, shaded Settings and Brightness controls, and Bright/Dim profiles](images/cove-native-tv.png)

Actual TV font, input inventory and installed renderer. No media content is captured.
The sample connections in the previews below can differ from the TV capture.

## Browser previews

## Apple TV

![Apple TV as the current input, with live brightness, Bright/Dim and Settings controls](images/cove-launcher.png)

## Sound settings shortcut

![Detected sound system with HDMI port and verified eARC capability, focused beside Brightness](images/cove-audio.png)

The sample audio endpoint is separate from the video cards. Its button opens
Samsung Sound settings; capability and port labels come from native reports
on the TV. The eARC label is omitted when capability is unknown.

## PlayStation 5

![PlayStation 5 as the current input, with brightness-only Bright/Dim controls](images/cove-playstation5.png)

## Nintendo Switch

![Nintendo Switch as the current input](images/cove-switch.png)

## Unnamed HDMI device

![Connected device with no supplied name shown as HDMI 4 with a generic connector graphic](images/cove-hdmi.png)

## Brightness: Current source

![Live brightness slider with Current source selected](images/cove-brightness-preview.png)

## Brightness: All sources

![Live brightness slider with All sources selected](images/cove-live-brightness.png)

The toggle controls Samsung's broader Apply Picture Settings option. A read-only
scope label replaces it when unavailable, as shown in the Game Mode preview.
See [brightness behavior](brightness.md).

## Customize a profile

![Dim brightness profile being edited](images/cove-dim-brightness.png)

![Bright brightness on a gaming input](images/cove-game-brightness.png)

## Input settling

![Brightness waits for a coherent native context instead of showing a stale value](images/cove-pending.png)

The ellipsis is temporary while the current picture context is unsettled.
Brightness and profiles become available after valid observations; ordinary
HDMI navigation remains separate. This preview illustrates the state, not the
TV's transition timing.

Regenerate offline images with `node scripts/capture-preview.cjs` after installing
the browser dependencies described in [regression testing](regression-testing.md).
The native capture is obtained and reviewed separately.

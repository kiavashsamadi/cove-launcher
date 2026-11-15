# Native typography

The launcher uses the TV's available font rather than downloading a typeface.
Browser previews use system fonts and may differ in glyph width, weight and
baseline. Native title bounds leave room for those differences so a device name
does not collapse into an ellipsis unnecessarily.

Device labels use the reported name, with generic HDMI fallback. Focus and
current-input status remain separate. Evaluate long names, numbers and non-Latin
labels against native rendering when adapting a different platform.

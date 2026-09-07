# 09: Overlay and guide render in fonts that exist

**What to build:** The overlay and the guide are drawn in the platform's own
interface and monospace fonts. The app currently names Windows fonts that
are not installed on macOS; they silently fall back to a substitute at
different metrics, which is why text in the overlay — the one part of the
app that is always on screen while dictating — looks subtly wrong against
its fixed pixel widths.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The overlay and guide use fonts confirmed present on the running
      platform
- [ ] Overlay text fits its fixed widths on macOS without clipping or
      overflow, checked against the rendered preview
- [ ] Windows rendering is unchanged
- [ ] Full suite green on macOS

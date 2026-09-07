# 08: The recording overlay stays on screen while you dictate elsewhere

**What to build:** While recording on macOS, the overlay is visible over
whatever app the user is dictating into, including a full-screen app. Today
it would disappear the moment focus moves — which is always, because a
menu-bar-only app is never the frontmost app. An overlay that vanishes
exactly when it is needed makes dictation a blind experience.

The framework exposes no API for this; the window has to be configured
natively once when shown. A prototype (`tests/probe_overlay_mac.py`)
established the working configuration and recorded its measured before/after
in the file:

```
setLevel_(101)                       # popUpMenu
setCollectionBehavior_(canJoinAllSpaces | stationary
                       | ignoresCycle | fullScreenAuxiliary)
setHidesOnDeactivate_(False)
setIgnoresMouseEvents_(True)
```

**Blocked by:** 07 (Menu-bar-only). The bug only manifests from an accessory
app; verifying it any earlier means faking the condition it fails under.

**Status:** done

- [x] The overlay stays visible after another application takes focus.
      Verified live from an accessory app by
      `tests/probe_overlay_pinned_mac.py`, which drives the *shipped*
      `WaveformOverlay` rather than a prototype: after Terminal was
      activated, `isVisible=True`
- [x] The overlay appears over a full-screen app — `fullScreenAuxiliary`
      plus `canJoinAllSpaces` are in the applied behaviour, and the probe
      reports `onActiveSpace=True` after focus moved away
- [x] The overlay never steals focus or swallows mouse input —
      `setIgnoresMouseEvents_(True)` on top of the existing
      `WA_ShowWithoutActivating` / `WindowTransparentForInput` flags
- [x] Windows overlay behaviour is unchanged — `wants_floating_overlay` is
      False off macOS, so `showEvent` does no extra work and no AppKit
      import is attempted
- [x] Full suite green on macOS (370 passed, 4 skipped; baseline 353 + 17)

**Found while implementing:** the pinning is applied on *every* show, not
once at construction. Qt can recreate a widget's native window between
hides, and the calls are idempotent, so re-applying is cheaper than tracking
whether the NSWindow behind `winId()` is still the same one.

`float_over_everything` answers False for a platform that does not need it, a
window that is not there yet, and an AppKit that refused — all three leave a
working app with Qt's own overlay behaviour. A missing pyobjc degrades the
overlay; it must not take down a dictation.

The measured `collectionBehavior` of 337 is asserted by name *and* by number
in `tests/test_mac_overlay_window.py`: the number is what the probe verified
on a real screen, so a change to it is a change to verified behaviour rather
than a refactor.

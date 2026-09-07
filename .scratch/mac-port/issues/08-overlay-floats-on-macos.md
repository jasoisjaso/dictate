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

**Status:** ready-for-agent

- [ ] The overlay stays visible after another application takes focus
- [ ] The overlay appears over a full-screen app
- [ ] The overlay never steals focus or swallows mouse input
- [ ] Windows overlay behaviour is unchanged
- [ ] Full suite green on macOS

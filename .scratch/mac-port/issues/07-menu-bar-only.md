# 07: Menu-bar-only, and Quit actually quits

**What to build:** On macOS Dictate lives in the menu bar with no Dock icon
and no Cmd+Tab entry — it matches what the app already is on Windows, a tray
app with no window. This is applied at startup so that a run from source
behaves identically to the bundle later, rather than the two differing in
the one behaviour being verified.

With no Dock icon and no window, the tray menu's Quit becomes the only way
out of the app, so that path has to genuinely exit rather than leave a
process behind.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Running on macOS shows a menu-bar icon and no Dock icon or Cmd+Tab
      entry. Verified live by `tests/probe_menu_bar_mac.py` on this machine:
      `activationPolicy` 0 (Regular) → 1 (Accessory), confirmed a second way
      through `NSRunningApplication.currentApplication()`
- [x] The tray menu is reachable and its items work — the same probe shows
      the tray still visible *after* the policy change (the failure mode if
      the wrong policy were chosen), and `smoke_boot.py` already exercises
      the menu actions
- [x] Quit exits the process cleanly, verified by the process being gone:
      the probe arms the watchdog and the process ends from inside it —
      `probe exit: 0`, and the line after `app.exec()` never printed
- [x] Windows tray behaviour is unchanged — `wants_menu_bar_only` is False
      off macOS, so neither the policy nor the watchdog is ever applied
- [x] Full suite green on macOS (353 passed, 4 skipped)

**Found while implementing:** the policy has to be applied after
`QApplication` (NSApp is the object Qt creates) and before `tray.show()`, or
the Dock icon appears for a moment first. Applying it from source rather than
relying on the bundle's `LSUIElement` is deliberate — a dev run and the
shipped `.app` must not differ in the one behaviour being verified.

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

**Status:** ready-for-agent

- [ ] Running on macOS shows a menu-bar icon and no Dock icon or Cmd+Tab
      entry
- [ ] The tray menu is reachable and its items work
- [ ] Quit exits the process cleanly, verified by the process being gone
- [ ] Windows tray behaviour is unchanged
- [ ] Full suite green on macOS

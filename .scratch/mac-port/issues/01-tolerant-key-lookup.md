# 01: Key lookup degrades instead of crashing

**What to build:** Dictate's hotkey listener starts on macOS. Today naming a
key that pynput does not define on this platform takes the whole listener
down before it binds anything, so no Trigger works at all. After this ticket
an unavailable key name is reported the same way an unrecognised one already
is — a warning and a fallback — and every other binding keeps working.

This is a prefactor: no user-visible feature, but nothing else on macOS can
be demonstrated until it lands.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Building the key table on macOS no longer raises; the hotkey listener
      starts and the app reaches its ready state
- [ ] A key name that does not exist on the running platform logs the
      existing unknown-key warning and falls back, rather than raising
- [ ] Windows key resolution is unchanged for every name it resolves today,
      covered by a test that runs on all platforms
- [ ] Full suite green on macOS (baseline: 246 passed, 4 skipped)

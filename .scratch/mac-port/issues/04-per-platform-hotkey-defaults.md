# 04: Hotkey defaults that exist on a Mac keyboard

**What to build:** Out of the box on macOS, push-to-talk is Right Option —
the key already under the user's right thumb, and one that stays inert while
held. Bindings that name keys the machine does not have, or that would fire
media and brightness functions on a bare press, are not shipped as defaults.
Copy-last-dictation stays bound, because it is the rescue path when text
lands in the wrong place.

The Settings key-picker offers only keys that exist on the running platform,
so a user cannot bind something unreachable.

Windows defaults are untouched.

See `docs/adr/0003-per-platform-hotkey-defaults.md`.

**Blocked by:** 01 (Key lookup degrades instead of crashing).

**Status:** ready-for-agent

- [ ] macOS push-to-talk defaults to Right Option; Windows still defaults to
      Right Ctrl
- [ ] No macOS default binds a key absent from the platform
- [ ] Copy-last-dictation remains bound on macOS
- [ ] Toggle, mode-cycle and re-record ship unbound on macOS and are
      settable in Settings for anyone who has turned on standard function
      keys
- [ ] The Settings key-picker lists only platform-available keys
- [ ] The per-platform default tables are covered by table-driven tests that
      run on every platform
- [ ] Full suite green on macOS

# 06: User data lives where a Mac user expects it

**What to build:** Settings, logs and the several-hundred-megabyte Model
cache land in the standard macOS application-support location for the app,
rather than the Linux-shaped directory macOS currently falls through to. It
matters because of the size: a user, an uninstaller, or Migration Assistant
should be able to find it.

Portable mode is untouched — a portable install still keeps everything
beside itself and writes nothing to the host.

No migration is needed; nothing has been written there yet.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] On macOS, settings, logs and Models resolve under the standard
      application-support location for the app
- [ ] Windows and portable-mode locations are unchanged
- [ ] Per-platform directory resolution is covered by tests that run on
      every platform
- [ ] Full suite green on macOS

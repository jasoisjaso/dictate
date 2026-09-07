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

**Status:** done

- [x] On macOS, settings, logs and Models resolve under the standard
      application-support location for the app. Verified live on this
      machine: `~/Library/Application Support/TranscribeDictate` with
      `models/`, `settings.toml` and `dictate.log` beneath it
- [x] Windows and portable-mode locations are unchanged — `%LOCALAPPDATA%`
      and `<install root>/Data` come back from the same resolver, and
      `tests/test_portable.py` still passes untouched
- [x] Per-platform directory resolution is covered by tests that run on
      every platform (`resolve_app_data_dir` takes system, env, home,
      install root and portable as arguments and creates nothing, so every
      platform's answer is asserted from every platform)
- [x] Full suite green on macOS (342 passed, 4 skipped)

**Found while implementing:** a Mac with `XDG_DATA_HOME` set — a stray shell
profile is enough — would have kept hiding the Models in a Linux-shaped
directory even after the Darwin branch was added, so the Darwin branch
ignores it deliberately, with a test that says so.

**Migration:** none needed, as the ticket said. The old
`~/.local/share/TranscribeDictate` on this machine holds an empty `models/`
and nothing else; it is left in place rather than deleted.

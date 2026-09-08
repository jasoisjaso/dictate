# 10: App Profiles work on macOS, and the tray tells the truth about hardware

**What to build:** Two things a mac user notices as one thing — the app
knowing what it is running on.

App Profiles: dictating into a terminal on macOS gets verbatim words rather
than sentence-cased prose, the same as on Windows. The Foreground App is
identified by its bundle identifier on macOS and by executable name on
Windows; a single match list holds both kinds, and the shipped defaults gain
mac patterns beside the Windows ones. Bundle identifier over display name
because it is stable and locale-independent.

Hardware probes: the Tier detection stops shelling out to Windows-only and
NVIDIA-only tools that cannot exist on this machine, and says honestly that
it is running on Apple Silicon CPU. The answer is already correct by
accident; this makes it correct on purpose and gives the tray something
truthful to show instead of an unexplained "cpu".

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Dictating into Terminal on macOS selects the terminal App Profile
- [x] Profile matching is covered by tests over both identifier kinds
- [x] Shipped default profiles match common mac terminals and editors as
      well as their Windows counterparts
- [x] Tier detection performs no Windows-only or NVIDIA-only probe on macOS
- [x] The tray and log state the CPU Tier with its reason
- [x] Windows detection and profile matching are unchanged
- [x] Full suite green on macOS

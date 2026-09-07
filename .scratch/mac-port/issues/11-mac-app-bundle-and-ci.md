# 11: A double-clickable Dictate.app, and macOS in CI

**What to build:** A Mac app the owner can double-click. It launches to the
menu bar, prompts for microphone access the first time it records, tells the
user how to grant Accessibility Permission if it is missing, downloads the
Model on first run with a progress bar, and then dictates. The Model is not
bundled — the download path already exists and keeps the app small enough to
move around.

Alongside it, the test suite runs on a macOS runner in CI. That is the only
automated thing standing between this port and a silent regression in either
direction, and Windows parity is a hard constraint.

See `docs/adr/0002-mac-app-bundle-and-signing.md`.

**Blocked by:** 03, 04, 05, 06, 07, 08, 09, 10.

**Status:** ready-for-agent

- [ ] A built app launches by double-click and reaches the ready state
- [ ] It declares a microphone usage description and the system prompt
      appears on first record; capture then returns real audio
- [ ] First run downloads the Model with visible progress and resumes after
      an interrupted attempt
- [ ] The built app is menu-bar-only, and its Quit exits cleanly
- [ ] End-to-end dictation works from the built app: hold Right Option,
      speak, words land at the cursor in another application
- [ ] CI runs the suite on macOS alongside the existing runners, green
- [ ] Manual smoke on Windows confirms unchanged behaviour before merge

# 03: macOS Input Backend — first dictation lands at the cursor

**What to build:** On a Mac, hold the Trigger, speak, release, and the words
appear at the cursor in whatever app has focus. This is the first end-to-end
dictation on macOS.

Short single-line text arrives by Type so the clipboard is untouched.
Multi-line text arrives by Paste, so a dictated newline can never send a
half-finished chat message. A failed Injection leaves the text on the
clipboard rather than losing it. The voice-edit commands that rewrite the
last injection — undo, replace X with Y, redo verbatim — work, which means
backspace and select-all behave as the delivery path expects.

**Blocked by:** 02 (One Injection interface).

**Status:** ready-for-agent

- [ ] Dictating into a text field on macOS puts the transcript at the cursor
- [ ] Multi-line output pastes; short single-line output types
- [ ] The clipboard is restored after a Paste, matching the Windows contract
- [ ] Undo, replace-X-with-Y and redo-verbatim each work on macOS
- [ ] A failed Injection parks the text on the clipboard and the user is told
- [ ] The fake-backend delivery tests from 02 pass unchanged; no Windows
      behaviour is altered
- [ ] Full suite green on macOS

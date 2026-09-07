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

**Status:** done

- [x] Dictating into a text field on macOS puts the transcript at the cursor
      (typed characters observed arriving through a real event tap)
- [x] Multi-line output pastes; short single-line output types
- [x] The clipboard is restored after a Paste, matching the Windows contract
      (pasteboard held our text at chord time, prior contents back after)
- [x] Undo, replace-X-with-Y and redo-verbatim each work on macOS — they go
      through backspaces/select_all/type, all posted and observed
- [x] A failed Injection parks the text on the clipboard and the user is told
- [x] The fake-backend delivery tests from 02 pass unchanged; no Windows
      behaviour is altered
- [x] Full suite green on macOS (278 passed, 4 skipped)

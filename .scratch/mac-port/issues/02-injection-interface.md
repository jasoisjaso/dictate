# 02: One Injection interface, Windows backend behind it

**What to build:** Delivery stops knowing which operating system it is on.
Every Injection today goes through a module named for Windows, called from
the delivery path in dozens of places. After this ticket the delivery path
calls one small interface — type, paste, backspace, select-all, plus the
pure choose-injection decision — and an Input Backend is resolved once, at
import.

No behaviour changes on Windows. This is the expand half of the change: the
new form exists beside the old, so the mac backend can be dropped in next
without touching delivery again.

The seam this creates is also the test seam: a fake Input Backend that
records the operations and payloads it was asked for makes the whole
delivery path — voice-edit commands, the whitespace-only special case, the
failed-injection clipboard rescue — verifiable on any platform, including
Windows CI.

See `docs/adr/0001-input-backend-seam.md`.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] The delivery path names no operating system and calls only the
      Injection interface
- [x] The Windows Input Backend implements that interface; existing Windows
      Injection tests still pass unchanged
- [x] choose-injection keeps its current behaviour and its current tests,
      now living in the shared layer
- [x] A fake Input Backend exists and the delivery path is tested through
      it on any platform: type vs paste selection, multi-line always
      pasting, whitespace-only typed directly, failed injection leaving text
      on the clipboard, and the voice-edit commands
- [x] Full suite green on macOS (269 passed, 4 skipped)

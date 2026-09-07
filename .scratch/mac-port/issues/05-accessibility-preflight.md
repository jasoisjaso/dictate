# 05: Accessibility preflight — say what is wrong, open the right pane

**What to build:** When Dictate lacks Accessibility Permission on macOS, it
says so plainly at startup and offers a button that opens the System
Settings pane where the grant is made. Without this the failure mode is
silent in both directions: the Trigger never fires and Injection does
nothing, with no error anywhere.

This lands before the bundle deliberately — it is the tool used to debug the
bundle's permission behaviour.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] On startup without the grant, a dialog explains that Dictate needs
      Accessibility Permission and what it is for — `PROMPT_MESSAGE` names
      both consequences (the key is never seen, text cannot be typed)
- [x] The dialog opens the correct System Settings pane. Verified for real on
      this machine: `open "x-apple.systempreferences:...?Privacy_Accessibility"`
      exits 0 and brings System Settings frontmost
- [x] With the grant present, startup is unchanged and no dialog appears
      (`run_preflight` returns before `ask` is ever called)
- [x] The check is a no-op on Windows — `accessibility_trusted` reports True
      off macOS, so nothing is gated and nothing is asked
- [x] The permission state is visible in the log so a bug report identifies
      it without a screenshot (`permission_summary`, logged unconditionally)
- [x] Full suite green on macOS (333 passed, 4 skipped)

**Found while implementing:** `AXIsProcessTrusted` is not a Quartz symbol —
pyobjc's lazy loader raises `AttributeError` for it there. It belongs to
HIServices (re-exported by ApplicationServices). The probe now asks the
frameworks that actually define it. The dead `mac_input.accessibility_trusted`
copy, which had the same bug and no caller, is gone; `permissions.py` is the
single probe.

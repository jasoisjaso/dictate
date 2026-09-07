# 05: Accessibility preflight — say what is wrong, open the right pane

**What to build:** When Dictate lacks Accessibility Permission on macOS, it
says so plainly at startup and offers a button that opens the System
Settings pane where the grant is made. Without this the failure mode is
silent in both directions: the Trigger never fires and Injection does
nothing, with no error anywhere.

This lands before the bundle deliberately — it is the tool used to debug the
bundle's permission behaviour.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] On startup without the grant, a dialog explains that Dictate needs
      Accessibility Permission and what it is for
- [ ] The dialog opens the correct System Settings pane
- [ ] With the grant present, startup is unchanged and no dialog appears
- [ ] The check is a no-op on Windows
- [ ] The permission state is visible in the log so a bug report identifies
      it without a screenshot
- [ ] Full suite green on macOS

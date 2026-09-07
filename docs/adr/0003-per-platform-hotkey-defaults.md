# 3. Hotkey defaults are per-platform, and unavailable keys degrade

Date: 2026-09-07
Status: Accepted

## Context

The shipped hotkey defaults were chosen for a Windows PC keyboard, and every
one of them is wrong on a MacBook Air:

- `push_to_talk_key = "ctrl_r"` — the M5 Air's bottom row is
  `fn / control / option / command / space / command / option`. There is no
  right Control key. pynput's macOS enum *has* `ctrl_r`, so the default fails
  silently rather than loudly: nothing is under the user's thumb.
- `pause_key = "pause"` — no such key on the keyboard, and no
  `keyboard.Key.pause` in pynput on macOS at all.
- `copy_key = "f8"`, `mode_cycle_key = "f7"`, `rerecord_key = "f6"`,
  `toggle_key = "f9"` — macOS ships `com.apple.keyboard.fnState` unset, so a
  bare press of those keys sends media/brightness. Confirmed unset on this
  machine.

Worse than any individual default: `parse_key` in `src/hotkeys.py` builds its
lookup table eagerly, naming `Key.pause`, `Key.scroll_lock`, `Key.menu` and
`Key.insert`. None of those exist in pynput on macOS, so the table raises
`AttributeError` on construction and `HotkeyController.start()` cannot run for
*any* key name. The app has no working hotkeys on macOS before a single line of
port work.

Measured, not assumed: synthetic holds of Right Ctrl, Left Cmd, Right Cmd and
Right Option all pair cleanly as down→up in pynput's macOS event tap, as do the
real F6–F9 keycodes (which is what `fn`+F-key produces).

## Decision

Defaults become per-platform rather than shared, and key lookup becomes
tolerant:

1. `parse_key` resolves names with `getattr(keyboard.Key, name, None)` and
   skips what is missing, so an unavailable name falls through to the existing
   "unknown key" warning path instead of taking the app down. This is a bug fix
   that applies to Windows too.
2. macOS push-to-talk is **Right Option (`alt_r`)**.
3. macOS `pause_key` is disabled — the key does not exist to bind.
4. `copy_key` **stays** on F8 on macOS. `toggle_key`, `mode_cycle_key` and
   `rerecord_key` are disabled by default there.

## Consequences

Right Option over Right Command is the substantive call. Both pair fine in the
tap, but a held Command turns every other keypress into a system shortcut fired
at whatever app you are dictating into — a stray key mid-take can Quit or
Close it. Right Option held alone is inert: it composes characters only when
you type *with* it, and during a push-to-talk hold you are not typing.

Keeping `copy_key` means accepting that on a default-configured Mac it is
`fn`+F8, not F8. That was judged worth it: copy-last-dictation is the rescue
path when text lands in the wrong place, so losing it costs more than the
awkward chord. The three conveniences that were disabled are not rescue paths,
and a default that silently changes screen brightness is worse than no default.

The price of diverging defaults is that "the push-to-talk key" is no longer one
answer. Documentation, the Settings key-picker, and any support conversation
now have to say which platform they mean.

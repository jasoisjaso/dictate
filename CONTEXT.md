# Context

The shared vocabulary of Dictate. Glossary only — no implementation details,
no plans. If a word here means something different in your head to what it
means in this file, that disagreement is the thing to resolve first.

## Speech

**Engine** — the runtime that turns audio into text. Two exist: Whisper and
Parakeet. Not the same thing as a Model.

**Model** — the weights an Engine loads (`small`, `large-v3-turbo`,
`parakeet-tdt-0.6b-v3`). One Engine can load several Models.

**Whisper** — the Engine that handles every language, spoken prompts,
hotwords, and the translate modes. The only Engine that can do Bosnian.

**Parakeet** — the CPU-first Engine covering 25 European languages. Cannot do
Bosnian, cannot take a prompt or hotwords, cannot translate. Punctuates
natively.

**Tier** — the (device, compute type, model size) combination chosen for the
detected hardware. Derived, never configured directly.

**Take** — one recording, from trigger to release. A Take produces at most one
Transcript.

**Transcript** — the raw words an Engine returned for a Take, before the Text
Pipeline touches them.

**Text Pipeline** — the Engine-agnostic post-processing that makes Dictate
feel like Dictate: spoken punctuation, filler removal, dictionary, transforms,
casing, optional polish. Shared by both Engines.

## Delivery

**Injection** — putting text into whatever application has focus. Distinct
from transcription: a Transcript that never reaches the target app is a lost
dictation.

**Type** — Injection by synthesising one keyboard event per character.
Invisible to the clipboard, native-feeling, slow for long text.

**Paste** — Injection by putting text on the clipboard and synthesising the
paste shortcut. Instant, and the only safe choice for multi-line text, because
a typed newline can send a chat message mid-sentence.

**Input Backend** — the per-operating-system implementation of Injection.
Windows and macOS each have one; they are interchangeable behind one small
interface.

**Accessibility Permission** — the macOS grant that lets a program observe and
synthesise keyboard events. Attached to a specific binary identity, not to a
user. Without it, both hotkeys and Injection silently do nothing.

## Interaction

**Trigger** — the key gesture that starts and stops a Take. Either
push-to-talk (hold) or toggle (tap on, tap off).

**Push-to-talk key** — the key held during a Take. A modifier-only key by
default, which is why its press/release pairing is a platform concern rather
than a detail.

**App Profile** — formatting rules selected by which application currently has
focus, so a terminal gets verbatim words while an email gets prose.

**Foreground App** — the application with focus right now. What an App Profile
matches against. How it is *named* is platform-dependent: Windows identifies it
by executable name (`cmd.exe`), macOS by bundle identifier
(`com.apple.Terminal`). One `match` list holds both kinds, so a profile is
portable even though an identifier is not.

## Scope

**Supported language** — a language the shipped configuration is tested and
answerable for. On macOS this is English only; Bosnian and the translate modes
remain Windows features. Unsupported is a statement about testing and support,
not about deleted code.

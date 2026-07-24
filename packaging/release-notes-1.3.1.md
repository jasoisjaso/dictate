## Dictate v1.3.1

Bug fix release. If you dictate long sentences, update.

### Fixed: app died silently after long dictations

Long dictations (anything over about 300 characters) are delivered by
clipboard paste instead of simulated typing. That clipboard code called
Windows APIs through ctypes without declaring 64-bit return types, so
clipboard handles were silently cut down to 32 bits. The result was a
garbage pointer and an instant access-violation crash the moment the
paste ran. Your words were already saved to history (F8 got them back),
but nothing was typed out and the app was dead in the tray.

Short dictations never touched the clipboard, which is why only long
sentences seemed cursed.

What changed:

- All clipboard and memory APIs now use explicit 64-bit safe signatures
- Clipboard reads are bounded by the real buffer size, never past it
- Clipboard open now retries briefly (clipboard managers hold the lock)
- The text is set and verified on the clipboard before Ctrl+V fires, so
  a paste can never insert your old clipboard contents by mistake
- If injection fails for any reason, the text lands on the clipboard
  and a toast tells you to press Ctrl+V - a dictation is never lost and
  the app never dies

### New: check for updates from Settings

Settings has a new About tab. It shows the version you are running and
a "Check for updates" button that asks the GitHub releases page. If a
newer version exists you are asked whether to open the download page;
nothing opens or downloads without your say-so.

### Downloads

- Dictate-Setup-gpu.exe - NVIDIA GPU build (bundles CUDA runtime, big
  download, fastest transcription)
- Dictate-Setup-cpu.exe - runs on any 64-bit Windows 10/11 PC

### Tests

170 automated tests pass on Windows, including new regression tests
that exercise the real Windows clipboard with paste-sized payloads.

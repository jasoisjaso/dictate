## Dictate v1.4.1

New feature: speak Bosnian, have it typed in English.

Nova funkcija: govorite bosanski, a tekst se kuca na engleskom.

### New: Speak Bosnian, write English

The language list has a new option:

    Speak Bosnian, write English (needs Ollama)

With it selected, anything you say in Bosnian (or a mix of Bosnian and
English) is typed out as English. Pure English speech passes through
untouched and stays fast.

How it works: the take is first written down exactly as you spoke it,
then a small local AI model (through Ollama, running on your own PC)
translates it to English. Nothing goes to the cloud. If Ollama is not
running, the app types the Bosnian text as spoken rather than losing
your words.

Turn it on: tray icon, Settings, Recognition tab, Language, pick
"Speak Bosnian, write English". Requires Ollama with a small model
installed; the app picks the fastest one you have automatically. A
Bosnian take lands as English in about five seconds; English takes are
unaffected.

Why not Whisper's built-in translate mode? The default GPU model
(large-v3-turbo) was shipped without the translation task and silently
ignores it; we verified this and routed around it. The translation
quality of a dedicated text model is also noticeably better on names
and workplace phrasing.

190 automated tests pass, including new ones covering the translation
path, the English fast path, and the Ollama-down fallback.

---

## Bosanski

### Novo: govorite bosanski, piše engleski

Lista jezika ima novu opciju:

    Speak Bosnian, write English (needs Ollama)

Sa njom uključenom, sve što kažete na bosanskom (ili mješavini
bosanskog i engleskog) biće otkucano na engleskom. Čisti engleski
govor prolazi netaknut i ostaje brz.

Kako radi: diktat se prvo zapiše tačno kako ste ga izgovorili, zatim ga
mali lokalni AI model (kroz Ollama, na vašem računaru) prevede na
engleski. Ništa ne ide u cloud. Ako Ollama nije pokrenuta, aplikacija
kuca bosanski tekst kako je izgovoren umjesto da izgubi vaše riječi.

Uključivanje: ikona u traci, Settings, tab Recognition, Language,
izaberite "Speak Bosnian, write English". Potrebna je Ollama sa malim
modelom; aplikacija sama bira najbrži koji imate. Bosanski diktat
stigne kao engleski za otprilike pet sekundi; engleski diktati su
nepromijenjeni.

Zašto ne Whisperov ugrađeni translate mod? Podrazumijevani GPU model
(large-v3-turbo) je isporučen bez zadatka prevođenja i tiho ga
ignoriše; to smo provjerili i zaobišli. Kvalitet prijevoda posebnog
tekstualnog modela je i primjetno bolji na imenima i poslovnim
frazama.

190 automatskih testova prolazi, uključujući nove koji pokrivaju put
prevođenja, brzi engleski put, i slučaj kada Ollama nije dostupna.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build (bundles CUDA runtime, big
  download, fastest transcription) / verzija za NVIDIA grafičke
  kartice (veliki download, najbrža transkripcija)
- Dictate-Setup-cpu.exe - runs on any 64-bit Windows 10/11 PC / radi
  na svakom 64-bitnom Windows 10/11 računaru

## Dictate v1.3.2

Follow-up fix. v1.3.1 stopped the crash on long dictations; v1.3.2
makes sure the text actually lands in the window, including terminals.

Nastavak ispravke. v1.3.1 je zaustavio pad kod dugih diktata; v1.3.2
osigurava da tekst zaista stigne u prozor, uključujući i terminale.

### Fixed: long dictations pasted into thin air in terminals

Long dictations are delivered by clipboard paste (a synthesized
Ctrl+V). That injected keystroke carried no hardware scan code, and
some apps, Windows Terminal first among them, drop injected keys
without one. The text sat safely on the clipboard but nothing appeared
in the window, so F8 plus a manual Ctrl+V was the workaround.

What changed:

- Injected keystrokes now carry real hardware scan codes, so the
  synthetic Ctrl+V looks like a physical keypress to every app
- The paste now waits (up to a second) for you to release the
  push-to-talk key first. Fast transcriptions could fire Ctrl+V while
  your finger was still on Right Ctrl, and the two merged into
  nothing. If the key stays held, the text is typed instead
- Terminal windows now always get single-line text typed, whatever its
  length. Terminals accept typed input reliably but are the app class
  most likely to eat a synthetic paste. Multi-line text still pastes,
  because a typed Enter would execute a half-finished shell line

Verified with a closed-loop test on a live window: a 346-character
paste and a typed short take both arrived intact, no rescue key
needed. 175 automated tests pass.

---

## Bosanski

### Ispravljeno: dugi diktati su se lijepili u prazno u terminalima

Dugi diktati se ubacuju lijepljenjem preko clipboarda (simulirani
Ctrl+V). Taj ubačeni pritisak tipke nije nosio hardverski scan kod, a
neki programi, prije svih Windows Terminal, odbacuju ubačene tipke bez
njega. Tekst je sigurno stajao na clipboardu, ali se ništa nije
pojavilo u prozoru, pa je F8 uz ručni Ctrl+V bio zaobilazni put.

Šta je promijenjeno:

- Ubačene tipke sada nose prave hardverske scan kodove, pa simulirani
  Ctrl+V izgleda kao fizički pritisak tipke svakom programu
- Lijepljenje sada sačeka (do jedne sekunde) da pustite tipku za
  diktiranje. Brze transkripcije su mogle okinuti Ctrl+V dok je prst
  još bio na desnom Ctrl, i ta dva su se spojila u ništa. Ako tipka
  ostane pritisnuta, tekst se kuca umjesto lijepljenja
- Terminali sada uvijek dobijaju jednolinijski tekst otkucan, bez
  obzira na dužinu. Terminali pouzdano primaju kucani unos, ali su
  klasa programa koja najčešće proguta simulirano lijepljenje.
  Višelinijski tekst se i dalje lijepi, jer bi otkucani Enter izvršio
  napola napisanu komandu

Provjereno testom sa stvarnim prozorom: lijepljenje od 346 znakova i
kratki otkucani diktat su oba stigla netaknuta, bez ikakve pomoćne
tipke. 175 automatskih testova prolazi.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build (bundles CUDA runtime, big
  download, fastest transcription) / verzija za NVIDIA grafičke
  kartice (veliki download, najbrža transkripcija)
- Dictate-Setup-cpu.exe - runs on any 64-bit Windows 10/11 PC / radi
  na svakom 64-bitnom Windows 10/11 računaru

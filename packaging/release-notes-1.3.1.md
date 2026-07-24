## Dictate v1.3.1

Bug fix release. If you dictate long sentences, update.

Ispravka greške. Ako diktirate duge rečenice, ažurirajte.

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

---

## Bosanski

### Ispravljeno: aplikacija se tiho gasila nakon dugih diktata

Dugi diktati (sve preko oko 300 znakova) ubacuju se u tekst preko
clipboarda (lijepljenjem), a ne simuliranim kucanjem. Taj clipboard kod
je pozivao Windows funkcije bez ispravnih 64-bitnih tipova, pa su
clipboard handle-ovi bili tiho skraćeni na 32 bita. Rezultat je bio
neispravan pokazivač i trenutni pad aplikacije (access violation) u
momentu lijepljenja. Vaše riječi su već bile sačuvane u historiji (F8
ih je vraćao), ali ništa se nije ukucalo i aplikacija je bila mrtva u
traci.

Kratki diktati nikad ne diraju clipboard, i zato su samo duge rečenice
izgledale uklete.

Šta je promijenjeno:

- Sve clipboard i memorijske funkcije sada koriste ispravne 64-bitne
  potpise
- Čitanje clipboarda je ograničeno stvarnom veličinom bafera, nikad
  preko nje
- Otvaranje clipboarda sada kratko pokušava ponovo (clipboard menadžeri
  ga znaju nakratko držati zaključanim)
- Tekst se postavi i provjeri na clipboardu prije nego što se pritisne
  Ctrl+V, tako da lijepljenje nikad ne može greškom ubaciti vaš stari
  sadržaj clipboarda
- Ako ubacivanje teksta iz bilo kojeg razloga ne uspije, tekst završi
  na clipboardu i obavijest vam kaže da pritisnete Ctrl+V - diktat se
  nikad ne gubi i aplikacija se nikad ne gasi

### Novo: provjera ažuriranja iz Postavki

Postavke imaju novi tab About. Prikazuje verziju koju koristite i dugme
"Check for updates" koje pita GitHub stranicu izdanja. Ako postoji
novija verzija, pita vas da li želite otvoriti stranicu za preuzimanje;
ništa se ne otvara niti preuzima bez vašeg odobrenja.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build (bundles CUDA runtime, big
  download, fastest transcription) / verzija za NVIDIA grafičke
  kartice (veliki download, najbrža transkripcija)
- Dictate-Setup-cpu.exe - runs on any 64-bit Windows 10/11 PC / radi
  na svakom 64-bitnom Windows 10/11 računaru

### Tests / Testovi

170 automated tests pass on Windows, including new regression tests
that exercise the real Windows clipboard with paste-sized payloads.

170 automatskih testova prolazi na Windowsu, uključujući nove
regresijske testove koji rade sa stvarnim Windows clipboardom i
sadržajem veličine pravog diktata.

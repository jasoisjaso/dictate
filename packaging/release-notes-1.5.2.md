## Dictate v1.5.2

Bug fix plus a privacy cleanup.

Ispravka greske i ciscenje privatnosti.

### Fixed: auto-punctuation did nothing until restart

Ticking "Auto-punctuation" in Settings saved correctly but did not
affect the app until it was fully restarted, so periods and capital
letters were not being added even with the box checked. Settings changes
now apply immediately to the running app. The same fix also makes
switching to Mixed mode in Settings safe without a restart.

### Privacy: removed personal paths from the public repo

Two build helper scripts had a full Windows user path hardcoded, and the
installer carried a private network address. Both are cleaned up: the
scripts use relative paths now, and the publisher link points to the
public GitHub page.

### Bosanski

Ukljucivanje "Auto-punctuation" u postavkama se ispravno cuvalo, ali
nije djelovalo na aplikaciju dok se potpuno ne restartuje, pa se tacke i
velika slova nisu dodavali ni kad je kvadratic bio ukljucen. Promjene u
postavkama se sada primjenjuju odmah. Ista ispravka cini i prebacivanje
na Mixed mod sigurnim bez restarta.

Privatnost: dvije pomocne skripte su imale punu Windows putanju upisanu,
a instalacioni fajl je nosio privatnu mreznu adresu. Oboje je ocisceno.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build / verzija za NVIDIA graficke
- Dictate-Setup-cpu.exe - any 64-bit Windows 10/11 PC / svaki racunar

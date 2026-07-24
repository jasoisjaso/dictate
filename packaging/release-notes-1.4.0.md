## Dictate v1.4.0

New feature release: dictate in English and Bosnian without touching a
single setting.

Nova funkcija: diktirajte na engleskom i bosanskom bez diranja ijedne
postavke.

### New: Mixed English + Bosnian mode

Until now the language setting was fixed. If it was set to English and
you spoke Bosnian, Whisper did not transcribe your words, it quietly
TRANSLATED them into English. Switching languages meant opening
Settings every time.

The language list now has a new option:

    Mixed: English + Bosnian (detects per take)

With Mixed selected, Dictate listens to each take and decides which of
your languages it hears, restricted to English, Bosnian, Croatian and
Serbian. Restricting the choice to your real languages keeps accuracy
high; full auto-detect has to guess between 100 languages and gets it
wrong more often. On long takes that stream in chunks, detection runs
per chunk, so if you switch language partway through a long dictation
the text comes out right from that chunk onward.

Turn it on: tray icon, Settings, Recognition tab, Language, pick Mixed.

Honest limitation, shared by every Whisper-based tool: a single
language is chosen per take (or per chunk on long takes). If you flip
language mid-sentence inside one short take, the whole take comes out
in whichever language dominated. Pause briefly when you switch and each
take lands in the right language. Commercial tools (Wispr Flow,
SuperWhisper) have the same per-session limitation.

Verified with real generated speech through the actual engine: a
Bosnian sentence and an English sentence through the same Mixed engine
each came out in their own language, while the old forced-English path
translated the Bosnian audio word for word. 182 automated tests pass.

---

## Bosanski

### Novo: mješoviti način, engleski + bosanski

Do sada je jezik bio fiksna postavka. Ako je bio podešen na engleski, a
vi progovorite bosanski, Whisper nije zapisivao vaše riječi nego ih je
tiho PREVODIO na engleski. Promjena jezika je značila otvaranje
postavki svaki put.

Lista jezika sada ima novu opciju:

    Mixed: English + Bosnian (detects per take)

Sa uključenim Mixed, Dictate sluša svaki diktat i odluči koji od vaših
jezika čuje, ograničeno na engleski, bosanski, hrvatski i srpski.
Ograničavanje izbora na vaše stvarne jezike drži tačnost visokom; puni
auto-detect mora pogađati između 100 jezika i češće griješi. Kod dugih
diktata koji se obrađuju u dijelovima, prepoznavanje se vrši po dijelu,
pa ako promijenite jezik usred dugog diktata, tekst izlazi ispravno od
tog dijela nadalje.

Uključivanje: ikona u traci, Settings, tab Recognition, Language,
izaberite Mixed.

Poštena napomena, važi za svaki alat baziran na Whisperu: jedan jezik
se bira po diktatu (ili po dijelu kod dugih). Ako prebacite jezik usred
jedne kratke rečenice, cijeli diktat izlazi na jeziku koji je
preovladao. Napravite kratku pauzu kad mijenjate jezik i svaki diktat
će izaći na pravom jeziku. Komercijalni alati (Wispr Flow,
SuperWhisper) imaju isto ograničenje po sesiji.

Provjereno stvarnim generisanim govorom kroz pravi engine: bosanska
rečenica i engleska rečenica kroz isti Mixed engine izašle su svaka na
svom jeziku, dok je stari put sa forsiranim engleskim preveo bosanski
zvuk riječ po riječ. 182 automatska testa prolaze.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build (bundles CUDA runtime, big
  download, fastest transcription) / verzija za NVIDIA grafičke
  kartice (veliki download, najbrža transkripcija)
- Dictate-Setup-cpu.exe - runs on any 64-bit Windows 10/11 PC / radi
  na svakom 64-bitnom Windows 10/11 računaru

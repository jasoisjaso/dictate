## Dictate v1.5.0

New feature: speak English, have it typed in Bosnian. The mirror of the
Bosnian-to-English mode added in 1.4.1.

Nova funkcija: govorite engleski, a tekst se kuca na bosanskom. Ogledalo
moda bosanski-na-engleski iz verzije 1.4.1.

### New: Speak English, write Bosnian

The language list has a new option:

    Speak English, write Bosnian (needs Ollama)

Say it in English (or mix English and Bosnian), the typed text comes out
in Bosnian, ijekavian with proper diacritics. Bosnian speech passes
through untouched.

How it works, same as the other direction: the take is written down as
you spoke it, then a local AI model (through Ollama, on your own PC)
translates it to Bosnian. Nothing leaves your machine. If Ollama is not
running, the app types the English text as spoken rather than losing
your words.

One honest note on speed and quality. The tiny fast models that are
perfect for Bosnian-to-English produce broken Bosnian in the other
direction (wrong words, Serbian ekavian drift). So this mode
deliberately picks a more capable model for correct ijekavian output,
which is slower: expect a few seconds per take once the model is warm.
The app pre-loads the model in the background at startup so the first
dictation is not the slow one, and keeps it in memory between takes.

Turn it on: tray icon, Settings, Recognition tab, Language, pick
"Speak English, write Bosnian".

Verified end to end on real speech with a local model: the English
sentence "Please send this report to the boss before the end of the
shift, it is very important" came out as "Molimo posaljite ovaj
izvjestaj sefu prije kraja smjene, veoma je vazan", correct ijekavian
with diacritics. 192 automated tests pass.

---

## Bosanski

### Novo: govorite engleski, pise bosanski

Lista jezika ima novu opciju:

    Speak English, write Bosnian (needs Ollama)

Recite na engleskom (ili mijesajte engleski i bosanski), otkucani tekst
izlazi na bosanskom, ijekavica sa ispravnim dijakriticima. Bosanski
govor prolazi netaknut.

Kako radi, isto kao i drugi smjer: diktat se zapise kako ste ga
izgovorili, zatim ga lokalni AI model (kroz Ollama, na vasem racunaru)
prevede na bosanski. Nista ne napusta vasu masinu. Ako Ollama nije
pokrenuta, aplikacija kuca engleski tekst kako je izgovoren umjesto da
izgubi vase rijeci.

Posteno o brzini i kvalitetu. Mali brzi modeli koji su savrseni za
bosanski-na-engleski prave losu bosansku recenicu u drugom smjeru
(pogresne rijeci, srpska ekavica). Zato ovaj mod namjerno bira jaci
model za ispravnu ijekavicu, koji je sporiji: ocekujte nekoliko sekundi
po diktatu kada se model zagrije. Aplikacija ucitava model u pozadini
pri pokretanju da prvi diktat ne bude spori, i drzi ga u memoriji izmedju
diktata.

Ukljucivanje: ikona u traci, Settings, tab Recognition, Language,
izaberite "Speak English, write Bosnian".

Provjereno stvarnim govorom sa lokalnim modelom: engleska recenica
"Please send this report to the boss before the end of the shift, it is
very important" izasla je kao "Molimo posaljite ovaj izvjestaj sefu
prije kraja smjene, veoma je vazan", ispravna ijekavica sa dijakriticima.
192 automatska testa prolaze.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build (bundles CUDA runtime, big
  download, fastest transcription) / verzija za NVIDIA graficke kartice
  (veliki download, najbrza transkripcija)
- Dictate-Setup-cpu.exe - runs on any 64-bit Windows 10/11 PC / radi na
  svakom 64-bitnom Windows 10/11 racunaru

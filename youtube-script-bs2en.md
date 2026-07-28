# YouTube skripta: "Govorim bosanski, kompjuter piše engleski"

Cilj: pokazati bs2en mod uzivo, reci sta treba od racunara, pokazati
instalaciju i svakodnevnu upotrebu. Duzina: 4 do 5 minuta.

PRIJE SNIMANJA (obavezno, 10 minuta):
- Restartuj Dictate, u Settings stavi language na
  "Translate: speak Bosnian, write English", sacekaj minutu da se
  model ugrije.
- Izgovori SVAKU recenicu iz ove skripte jednom kao probu. Ako neka
  ne ispadne dobro, zamijeni je. Snimaj samo recenice za koje znas
  da rade.
- Windows display scaling na 125-150% da se tekst vidi na telefonu.
- Ugasi notifikacije (Focus assist on).
- Govori pune recenice, 4-5 sekundi minimum. Prekratke fraze zna
  pogresno prepoznati kao engleski.

-----------------------------------------------------------------------

## 1. HLADNI START, BEZ UVODA (0:00 - 0:20)

EKRAN: WhatsApp Web ili Word, kursor u praznoj poruci. Odmah drzis
Right Ctrl i govoris.

GOVORIS (bosanski):
  "Stizem kuci za dvadeset minuta, treba li ti nesto iz prodavnice?"

NA EKRANU SE ISPISE (engleski, samo od sebe):
  "I'll be home in twenty minutes, do you need anything from the shops?"

GOVORIS (u kameru / voiceover):
  "Ja sam upravo govorio bosanski. Kompjuter je napisao engleski.
  Bez interneta, bez pretplate, bez slanja mog glasa bilo kome.
  Sve radi na mom racunaru. Pokazacu vam kako."

[TITLE CARD: Dictate. Govori bosanski, pisi engleski. Besplatno.]

-----------------------------------------------------------------------

## 2. STA JE OVO (0:20 - 0:50)

GOVORIS:
  "Program se zove Dictate. Napravio sam ga jer nijedan alat za
  diktiranje ne razumije nas jezik kako treba. Drzis jednu tipku,
  pricas, pustis tipku, i tekst se pojavi tamo gdje ti je kursor.
  U Wordu, u mejlu, u WhatsAppu, bilo gdje.

  Moze pisati bosanski kad govoris bosanski. A moze i ovo sto ste
  vidjeli: vi pricate na nasem, a on pise na engleskom. Za mejl
  sefu, za poruku, za CV. I obrnuto: govorite engleski, pise
  bosanski."

EKRAN: dok ovo pricas, prikazi tray ikonu, drzanje Right Ctrl,
talasni overlay dok govoris.

-----------------------------------------------------------------------

## 3. STA VAM TREBA (0:50 - 1:40)

EKRAN: jednostavna lista na ekranu, stavka po stavka.

GOVORIS:
  "Sta vam treba da bi ovo radilo:

  Prvo, Windows 10 ili 11.

  Drugo, za obicno diktiranje, bilo koji noviji racunar. Radi cak
  i bez graficke kartice, samo malo sporije i s manjim modelom.

  Trece, i ovo je bitno: za PREVODENJE, ovo govori bosanski pise
  engleski, treba vam Nvidia graficka kartica sa najmanje 6
  gigabajta memorije, a preporucujem 8 ili vise. Ja imam RTX 4060
  Ti sa 16 giga i prevod stigne za dvije-tri sekunde. Na slabijim
  karticama radi, samo sporije.

  Cetvrto, oko 10 gigabajta slobodnog prostora na disku, jer se
  modeli skinu jednom i poslije toga sve radi bez interneta.

  I peto, mikrofon. Ne mora biti skup, ja koristim obican."

[NA EKRANU, lista:]
  - Windows 10 / 11
  - Diktiranje: bilo koji racunar (GPU nije obavezan)
  - Prevodenje: Nvidia GPU, 6 GB VRAM minimum, 8+ GB preporuceno
  - ~10 GB prostora na disku
  - Mikrofon (bilo koji)
  - Internet samo za prvo skidanje, poslije sve offline

-----------------------------------------------------------------------

## 4. INSTALACIJA (1:40 - 2:50)

EKRAN: screen recording, korak po korak.

GOVORIS:
  "Instalacija ima dva dijela.

  Prvi dio: skinete Dictate sa GitHuba, link je u opisu. Kliknete
  na Releases, skinete installer, pokrenete ga. Ne treba vam admin
  nalog. Windows ce vam mozda pokazati plavi prozor da ne poznaje
  aplikaciju, kliknete 'More info' pa 'Run anyway'. To je zato sto
  je program besplatan i nije placen certifikat, kod je javan na
  GitHubu pa svako moze provjeriti sta radi.

  Drugi dio, samo ako hocete prevodenje: instalirate Ollama, to je
  besplatan program koji vrti male AI modele lokalno na vasoj
  grafickoj. Odete na ollama.com, skinete, instalirate. Onda
  otvorite terminal i ukucate jednu komandu:"

[NA EKRANU, krupno:]
  ollama pull dolphin3:8b

GOVORIS:
  "To skine model za prevodenje, oko pet gigabajta, jednom i
  nikad vise. I to je to. Dictate ga sam nade i sam ga koristi."

EKRAN: pokazi Dictate Settings, dropdown Language, odaberi
"Translate: speak Bosnian, write English", klikni Save.

GOVORIS:
  "U podesavanjima samo promijenite jezik na 'speak Bosnian, write
  English'. Poslije pokretanja programa sacekajte minutu da se
  model ucita u karticu, prvi put. Poslije ide odmah."

-----------------------------------------------------------------------

## 5. DEMO IZ ZIVOTA (2:50 - 4:10)

Tri scene, tri stvarne situacije. Svaku recenicu prvo probaj van
snimanja.

SCENA A: MEJL SEFU (Outlook ili Gmail)
GOVORIS (bosanski):
  "Postovani, javljam se u vezi sa isporukom za petak. Mozemo li
  pomjeriti utovar na osam sati ujutro? Hvala unaprijed."
EKRAN ISPISE (otprilike):
  "Hello, I'm writing regarding Friday's delivery. Could we move
  the loading to eight in the morning? Thank you in advance."
GOVORIS:
  "Mejl sefu na engleskom, a ja engleski nisam ni progovorio."

SCENA B: POSAO / SVAKODNEVNICA (Word ili Notepad)
GOVORIS (bosanski):
  "Danas sam radio u skladistu i bilo je jako hladno, moram sutra
  ponijeti rukavice."
EKRAN ISPISE:
  "Today I worked in the warehouse and it was very cold, I have to
  bring gloves tomorrow."
  (ova je testirana, radi tacno ovako)

SCENA C: OBRNUTI SMJER, KRATKO
EKRAN: Settings, promijeni na "speak English, write Bosnian".
GOVORIS (engleski):
  "The delivery truck will arrive tomorrow at seven thirty."
EKRAN ISPISE (bosanski):
  prevod na bosanskom
GOVORIS:
  "Radi i naopako. Govorite engleski, pise bosanski. Za poruke
  rodbini kad vam mozak radi na engleskom poslije cijelog dana
  posla."

-----------------------------------------------------------------------

## 6. ZAVRSETAK (4:10 - 4:40)

GOVORIS:
  "Program je potpuno besplatan i kod je javan. Link za skidanje
  je u opisu. Nista ne ide na internet, vas glas ostaje na vasem
  racunaru.

  Ako vam nesto ne radi, pisite u komentar, citam sve. I recite
  mi: sta biste jos htjeli da ovo moze? Napravio sam ga za sebe,
  ali ako pomogne jos nekom nasem covjeku, super.

  Zivjeli."

[END CARD: github.com/jasoisjaso/dictate + "Besplatno. Offline. Nase."]

-----------------------------------------------------------------------

## NASLOV / OPIS / TAGOVI (za YouTube SEO)

Naslov (opcije, biraj jednu):
  1. Govorim BOSANSKI, kompjuter pise ENGLESKI (besplatan program)
  2. Diktiranje na bosanskom koje STVARNO radi (i prevodi na engleski)
  3. Napravio sam program: govoris nas jezik, pise engleski

Thumbnail: tvoje lice + strelica: "GOVORIS: bosanski" -> "PISE:
engleski". Krupna slova, dvije boje.

Opis (prvi red je najbitniji):
  Govorite bosanski, a racunar pise engleski. Besplatan program za
  diktiranje koji radi potpuno offline, bez pretplate.
  Skini: https://github.com/jasoisjaso/dictate/releases
  Za prevodenje treba i Ollama: https://ollama.com
  Komanda za model: ollama pull dolphin3:8b
  0:00 Demo
  0:20 Sta je Dictate
  0:50 Sta vam treba od racunara
  1:40 Instalacija
  2:50 Primjeri iz zivota
  4:10 Kraj

Tagovi: diktiranje bosanski, speech to text bosnian, prevod bosanski
engleski, glasovno kucanje, whisper ai bosanski, besplatan program,
diktiranje hrvatski, diktiranje srpski

-----------------------------------------------------------------------

## TEHNICKE NAPOMENE ZA SNIMANJE

- Svaka scena posebno, pa spoji u montazi. Ne mora iz prve.
- Poslije svake promjene moda u Settings sacekaj da se model ugrije
  (prvi take poslije promjene moze kasniti do minute).
- Ako take ispadne los: F6 je re-record, F8 kopira zadnji tekst.
- U demo scenama zumiraj na polje gdje se tekst ispisuje (crop u
  montazi je dovoljan).
- Diakritike (c, s, z) u ovoj skripti su namjerno bez kvacica da se
  fajl lako cita u terminalu; govoris normalno, naravno.
- Ne obecavaj savrsen prevod u videu. Reci "mali lokalni AI model,
  za savrsen prevod uvijek procitaj prije slanja". Iskreno = manje
  ljutih komentara.

## Dictate v1.5.3

Cetiri ispravke. Prevod na bosanski i engleski sada stvarno radi,
konacno je vidljiv u podesavanjima, i program se moze normalno ugasiti.

### Prevod (govori bosanski, pise engleski, i obrnuto) sada radi

Ova opcija je bila ugradena jos od verzije 1.4.1, ali nikad nije
stvarno funkcionisala. Postojala su dva odvojena problema.

Prvi problem: ova opcija se uopste nije mogla ukljuciti iz
podesavanja. Padajuci meni za jezik u Settings nikad nije dobio ove
dvije stavke, pa je jedini nacin da se ukljuci bio rucno mijenjanje
fajla sa postavkama. Sad su obje opcije vidljive u meniju: "Translate:
speak Bosnian, write English" i "Translate: speak English, write
Bosnian".

Drugi problem: cak i kad bi neko rucno ukljucio ovu opciju, prevod je
cesto tiho otkazivao i na ekranu bi ostao tekst onako kako je izgovoren,
bez ikakve poruke o gresci. Uzrok je bio model koji se koristio za
prevod sa engleskog na bosanski, model se ucitavao u graficku karticu
i po tri i po minute na nekim racunarima, a program je cekao samo
minut. Sad se za prevod na bosanski koristi drugi, brzi model koji
daje ispravan bosanski jezik, i koji je vecini korisnika vec ucitan u
memoriju jer se koristi i za ispravljanje gramatike. Za prevod sa
bosanskog na engleski takode je promijenjen model, jer je stari
model znao pogresno prevesti obicne rijeci, na primjer rijec
"skladiste" je prevodio kao "archive" umjesto "warehouse". Program
sad i ceka duze prije nego sto odustane, kako spor racunar ne bi
izgubio prevod bez razloga.

### Program sad ima dugme za gasenje

U meniju koji se otvara klikom na ikonicu u sistemskoj traci, dugme
za gasenje programa (Quit) je znalo nestati, a s njim i neke druge
stavke poput Copy last, History i Guide. Uzrok je bila greska u kodu
gdje su te stavke menija ostajale bez vlasnika i Python bi ih obrisao
iz memorije cim bi se meni napravio. Sad su ispravno vezane za meni i
ostaju vidljive.

### Notepad u Windows 11 vise ne gubi rijeci

Novi Notepad koji dolazi sa Windows 11 iz Microsoft Store ima spor
sistem za primanje teksta, pa je znao da uzme samo prvu rijec
diktiranog teksta a ostatak ostane prazan. Program sad prepoznaje
Notepad i tekst ubacuje preko clipboarda umjesto kucanjem, sto radi
pouzdano. Svaki drugi program i dalje radi kao i do sad.

### Sta vam treba za prevod

Ako zelite da koristite prevod (govori bosanski, pise engleski, ili
obrnuto), potrebna vam je Nvidia graficka kartica sa najmanje 6
gigabajta memorije, a preporuceno 8 ili vise, plus instaliran program
Ollama (besplatan, ollama.com) i model koji se skine jednom komandom
u terminalu:

ollama pull dolphin3:8b

Za obicno diktiranje, bez prevoda, graficka kartica nije neophodna.

## Preuzimanja

Dictate-Setup-gpu.exe, za racunare sa NVIDIA graficnom karticom.

Dictate-Setup-cpu.exe, za bilo koji 64-bitni Windows 10 ili 11 racunar.

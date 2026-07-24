## Dictate v1.5.1

Bug fix. Mixed mode is working again.

Ispravka. Mjesoviti mod ponovo radi.

### Fixed: Mixed mode captured nothing

The Mixed / auto values in the language menu are internal settings, not
real Whisper language codes. One of them was reaching the speech engine
directly, which rejected it and aborted the whole take, so pressing the
key and talking produced nothing and F8 said no speech was captured.

Fixed with a hard guard: the language setting now always resolves to a
real code or plain auto-detect before it can reach the engine. This
whole class of error is now impossible.

Also: the two experimental translate modes (speak one language, type
another) have been removed from the language menu for now. They needed
extra software running and were not ready. Mixed mode, which needs
nothing extra and just types whatever language you speak, stays and is
the recommended option.

### Bosanski

Vrijednosti Mixed / auto u meniju jezika su interne postavke, nisu
pravi Whisper kodovi jezika. Jedna od njih je stizala direktno do
govornog motora koji ju je odbio i prekinuo cijeli diktat, pa pritisak
tipke i govor nisu davali nista, a F8 je rekao da nista nije snimljeno.

Ispravljeno cvrstom zastitom: postavka jezika se sada uvijek svede na
pravi kod ili obicno auto-prepoznavanje prije nego stigne do motora.
Ova vrsta greske je sada nemoguca.

Takodje: dva eksperimentalna moda za prevodjenje (govoris jedan jezik,
pise drugi) su za sada uklonjena iz menija jezika. Trazili su dodatni
softver i nisu bili spremni. Mjesoviti mod, koji ne treba nista dodatno
i samo kuca jezik koji govoris, ostaje i preporucen je.

---

### Downloads / Preuzimanja

- Dictate-Setup-gpu.exe - NVIDIA GPU build / verzija za NVIDIA graficke
- Dictate-Setup-cpu.exe - any 64-bit Windows 10/11 PC / svaki racunar

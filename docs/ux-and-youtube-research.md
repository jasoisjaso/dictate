# Dictate — UX/feature research + YouTube video plan
_Research date: 2026-07-12. Sources: DeepSeek market/UX synthesis + live web (Wispr Flow, Superwhisper, Handy, VoiceInk, OpenWhispr, Reddit r/ProductivityApps, r/windowsapps)._

---

## TL;DR — where you sit in the market

You've built a **free, fully-local, offline, Windows** Whisper dictation app.
That is EXACTLY the lane people are hunting for right now. The paid tools are
Mac-first and subscription:

| Tool | Platform | Price | Notes |
|---|---|---|---|
| **Wispr Flow** | Mac/Win/iOS | **~$15/mo** ($12/mo annual) | polished, cloud-leaning, cross-device |
| **Superwhisper** | macOS only | **~$8/mo or $249 lifetime** | per-app "modes", local models |
| **Dragon** | Windows | $300–500 one-time, abandoned | legacy, no real updates |
| **Windows Win+H** | Windows | free | online, no custom words, weak punctuation |
| **Handy** | Win/Mac/Linux | **free, open-source, local** | THE current reddit darling in your lane |
| **VoiceInk / OpenWhispr / Voibe / LotusQ** | mixed | free/cheap local | your direct competitors |

**Your natural pitch:** _"Superwhisper's per-app 'modes' and Wispr's polish — but
free, on Windows, and your voice never leaves the machine."_ You already have the
per-app profiles (the thing Superwhisper charges a lifetime fee for). Lean into it.

---

## PART 1 — EASY UX/UI WINS (ranked by effort→impact)

These are the low-effort, high-demo-value features. Rough effort in hours.

### Tier A — do these first (each < ~1–2h, all demo beautifully)

1. **"Dictated N words · Ctrl+Z to undo" toast** after each injection. (~0.5h)
   Builds instant trust ("I won't lose my work"). Demos great on camera.
   You already track `last_injected_len` — just surface it in the overlay.

2. **Friendly error toasts for the silent-fail paths** (~0.5h). No mic, no
   speech detected, model still loading, GPU fell back to CPU. Right now some
   of these are log-only. A tray/overlay message = "feels robust."

3. **Session stats**: words dictated this session + words-per-minute, shown in
   the tray menu and History window (~1h). Cheap, and a killer on-screen stat
   for the video ("I've dictated 4,200 words today without touching the keyboard").

4. **Copy-last-dictation hotkey** (~0.5h) — a global key that copies the last
   result to clipboard. The #1 rescue when text lands in the wrong window.

5. **Overlay shows the detected app-profile** while recording (~0.5h) —
   e.g. a tiny "terminal · verbatim" / "email · professional" tag in the pill.
   Makes your best feature *visible* instead of invisible. Huge for the demo.

### Tier B — slightly more effort, strong payoff (each ~2–4h)

6. **"Redo last as verbatim" / re-run toggle** — if cleanup mangled something,
   re-inject the raw transcript. Pairs with the undo you already have.

7. **Pause/mute indicator + peak-level clipping warning** in the overlay — if
   the mic is too hot or silent, tell them mid-record. Prevents "why is it blank."

8. **First-run wizard polish**: a 3-step guided flow (pick mic → test it by
   speaking one line and SEE it transcribe → set your hotkey). The "speak one
   line and watch it work" moment is what converts a first-time user.

9. **Settings search / "test my setup" button** that records 3s and shows the
   result inline, so users validate mic+model without leaving Settings.

### Tier C — flagship features that move you ahead of the free pack (bigger)

10. **Voice editing commands** — this is the #1 thing reviewers say free tools
    lack. You already have `scratch that`. Add: `capitalize that`, `delete last
    word`, `select last sentence`, `all caps`, `undo that`. Even a handful lifts
    you above Handy/OpenWhispr. (This is your headline "tool not toy" feature.)

11. **Custom voice macros / snippets** — say "insert my email" → types your
    address; "sign off" → your signature. Cheap to build on the dictionary
    engine you already have, and it's a genuine Superwhisper-tier feature.

12. **Dictation "modes" you can switch by hotkey** (prose / code / command /
    email) rather than only auto-detected by app. Superwhisper's paid headline;
    you can do it free and it demos instantly.

---

## PART 2 — WHAT USERS ACTUALLY COMPLAIN ABOUT (fix = differentiation)

Prioritized from the power-user pain research. Map to what you already have:

1. **Names/jargon get mangled** → you have the personal dictionary + Whisper
   spelling boost. ✅ Already ahead. Show it on camera with hard words.
2. **Latency / "delay then dump"** → your live-preview pill (GPU) directly
   answers this. ✅ Lean on it; it's rare in free tools.
3. **Punctuation is dumb** → you have spoken punctuation + optional Ollama
   grammar pass. Consider auto-punctuation on by default for prose profiles.
4. **Editing by voice is missing** → your biggest GAP vs "pro" feel. See #10
   above. This is the single highest-leverage thing to build next.
5. **No per-app behaviour** → you already nailed this. Most tools can't. ✅
6. **Privacy/cloud fear** → you're 100% local. ✅ This is your whole brand.

**Net:** you're strong on 1, 2, 5, 6 (the hard ones). The one gap that would
make you feel like a paid tool is **voice-driven editing (#10)**.

---

## PART 3 — THE YOUTUBE VIDEO

Working title options (pick the punchiest thumbnail):
- **"I made a FREE dictation app that never touches the internet"**
- **"The free Windows app that ends your Dragon / Wispr subscription"**
- **"I deleted my keyboard for a week (free, 100% offline dictation)"**

### The hook (first 15–20s) — must answer "why care?" instantly
- Screen-record live dictation into Notepad, then **physically turn Wi-Fi off /
  disable the network adapter on camera** and keep dictating flawlessly.
- Overlay text: _"Free. Offline. Local Whisper. Built by one guy."_
- Line: "My internet is OFF and it still nails every word — no subscription,
  no cloud, no account."

### Segment map (aim ~10–13 min)
1. **Hook** (0:00–0:20)
2. **The problem** (0:20–1:00) — Wispr is $15/mo, Superwhisper is Mac-only,
   Windows' own Win+H needs the cloud and can't learn your words. Set the stakes.
3. **Install & first run** (1:00–2:30) — show it warts-and-all: the unsigned-
   installer SmartScreen warning (be honest — turns a negative into trust), the
   one-time model download with the progress bar, the first-run wizard. Honesty
   here = credibility.
4. **The demo gauntlet** (2:30–5:30) — dictate into email, VS Code, Word, a
   browser, a Discord box, switching windows mid-sentence. Throw HARD words at
   it (names, "Kubernetes", "Woolworths", your warehouse jargon) to show the
   dictionary. This is the "wow, it actually works" stretch.
5. **The killer differentiator — per-app awareness** (5:30–6:30) — dictate the
   same sentence into a terminal (verbatim, no casing) vs an email (professional).
   Show the profile tag in the pill. Line: "this is the 'Super Mode' the paid
   Mac apps charge a lifetime fee for — running free, on Windows, offline."
6. **Editing by voice** (6:30–7:30) — "scratch that", and whatever you build
   from Part 2 #10. This is the segment that makes people share it.
7. **PROVE the privacy** (7:30–8:30) — the trust segment nerds demand:
   - Show GlassWire / Resource Monitor with **zero outbound network** while
     dictating.
   - Wi-Fi already off from the hook.
   - Show the GitHub repo; point at the line that only network call is the
     one-time model download.
   - Line: "your voice never becomes data anywhere but your own RAM."
8. **Benchmarks** (8:30–10:00) — nerds live for this:
   - State your hardware (and ideally test on a weak laptop too).
   - Real-time factor: dictate 300 words, show near-instant on GPU.
   - Model size vs accuracy vs RAM table (tiny→small→large-v3-turbo).
   - Word error rate on a fixed sentence list if you can.
9. **Comparison table** (10:00–11:00) — same sentence into Win+H vs Wispr vs
   yours, scored on latency / accuracy / punctuation / price. You win on price
   and privacy by definition; show you're competitive on the rest.
10. **Outro / CTA** (11:00–end) — where to download, "it's free and open,
    star the repo", tease the roadmap (voice editing, macros).

### What makes it pop vs flop
POP:
- **Underdog framing**: "one person built what a billion-dollar company charges
  monthly for." That story travels.
- **The Wi-Fi-off moment** is your shareable clip. Put it early AND in the trailer.
- **Impeccable audio in the video itself** — you're selling dictation; bad mic
  audio = instant distrust. Non-negotiable.
- Show a REAL workflow ("here's how I wrote this whole script by voice"), not a
  feature checklist.

FLOP traps:
- Rambling Whisper-architecture tangents — timestamp/chapter them off.
- Skipping the setup — looks like you're hiding friction.
- Only showing "press key, speak" — viewers assume it's a toy. Show editing.
- Not comparing to Win+H — casual viewers think "my PC already does this."

### Thumbnail
Split screen: a crossed-out "$15/mo" / Dragon box on one side, a glowing
"FREE · OFFLINE" badge + your app's pill on the other. Face optional but a
genuine surprised reaction outperforms.

---

## Recommended build order before filming
1. App-profile tag in the overlay (Part1 #5) — makes your best feature visible.
2. Undo/word-count toast + session stats (Part1 #1, #3) — trust + on-screen stat.
3. A few voice-editing commands (Part1 #10) — the "it's a real tool" segment.
4. Friendly error toasts (Part1 #2) — so nothing fails silently on camera.

Those four are ~1 day of work total and directly create your best video moments.

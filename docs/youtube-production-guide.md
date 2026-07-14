# Dictate YouTube Video — Complete Production Guide

You don't need to show your face. You don't need to be a good speaker. This guide walks you through everything step by step, from installing the recording software to uploading the finished video.

---

## THE APPROACH: SCREEN RECORDING + VOICEOVER

You will NOT be on camera. The video is 100% screen recording with your voice narrating over it. This is how most software demo videos work — the viewer watches the app in action while you explain what's happening.

If you're not confident talking live, you can record the screen actions FIRST (no audio), then record your voice SEPARATELY while watching the playback, then combine them in editing. This is called "post-recorded voiceover" and it's much easier — you can re-record a sentence as many times as you want without having to redo the screen recording.

---

## STEP 1: INSTALL THE TOOLS (10 minutes)

You need two free programs:

### 1. OBS Studio (for screen recording)
- Go to https://obsproject.com
- Download the Windows version
- Install it (default settings are fine)

### 2. CapCut (for editing)
- Go to https://www.capcut.com (or search "CapCut" in the Microsoft Store)
- Download the Windows desktop version
- Install it

That's it. Two tools, both free, no watermarks.

---

## STEP 2: SET UP OBS STUDIO (5 minutes)

OBS looks complicated but you only need it to do one thing: record your screen.

1. Open OBS Studio
2. In the "Sources" box (bottom left), click the **+** button
3. Select **Display Capture**
4. Click OK on the popup (default settings are fine)
5. You should now see your desktop in the preview

### Audio settings:
1. In the "Mixer" box (bottom right, next to Sources), you'll see "Desktop Audio" and "Mic/Aux"
2. We want to record BOTH — the desktop audio (so viewers hear the beeps from Dictate) AND your microphone (your voiceover)
3. Make sure neither is muted (no red line through them)
4. Click **Settings** (bottom right) -> **Output** -> set "Recording Path" to a folder you'll remember (like Desktop)
5. Settings -> **Video** -> set "Base Resolution" and "Output Resolution" to **1920x1080**
6. Settings -> **Video** -> set "FPS" to **30**
7. Click OK

### Test recording:
1. Click **Start Recording** (bottom right)
2. Wait 5 seconds
3. Click **Stop Recording**
4. Check the folder — there should be an MP4 file. Open it to make sure it recorded your screen and audio.

---

## STEP 3: PREPARE YOUR SCREEN (5 minutes)

Before hitting record, make your screen look clean:

1. **Close everything** — browser, Discord, Steam, any notifications
2. **Desktop wallpaper** — set to a solid dark colour (right-click desktop -> Personalise -> pick a dark grey). This makes the video look cleaner.
3. **Taskbar** — set to auto-hide (right-click taskbar -> Taskbar settings -> "Automatically hide the taskbar")
4. **Open these windows** and arrange them so they're ready:
   - Notepad (blank, maximised)
   - WordPad (blank)
   - Windows Terminal / PowerShell
   - An email draft (Outlook or Gmail in browser)
   - Discord (if you have it)
5. **Pin the Wi-Fi toggle** — click the network icon in the system tray so it's quick to access. You need to turn off Wi-Fi mid-recording for the hook shot.
6. **Make Dictate is running** — the green mic icon should be in the system tray
7. **Set the language** — right-click the tray icon -> Settings -> Language -> English (or Bosnian for the Bosnian video)
8. **Set the visualizer** — Settings -> Visualizer -> Blob (or Equalizer, your choice)
9. **Zoom level** — set Windows display scaling to 100% (Settings -> Display -> Scale -> 100%). This makes text bigger and clearer in the recording.

---

## STEP 4: RECORD THE VIDEO (30-45 minutes)

You'll record in SEGMENTS. Each segment is a separate recording. This way if you mess up, you only redo that segment, not the whole video.

### How to record a segment:
1. In OBS, click **Start Recording**
2. Do the action on screen
3. Click **Stop Recording**
4. The file saves to your folder automatically

### The segments to record (in order):

**SEGMENT 1: THE HOOK (0:00 - 0:20)**
- Start recording
- Open Notepad (full screen)
- Hold Right Ctrl, dictate: "This is a test of offline dictation."
- While STILL holding Right Ctrl, click the Wi-Fi icon and turn off Wi-Fi
- Keep holding Right Ctrl, dictate: "My internet is off and this still works perfectly."
- Release Right Ctrl. Text appears.
- Stop recording
- NOTE: You don't need to talk in this segment — the dictation IS the audio. You'll add voiceover later.

**SEGMENT 2: PUSH-TO-TALK DEMO (2-3 min)**
- Start recording
- Open fresh Notepad
- Hold Right Ctrl, dictate: "Hey team comma new line just confirming the pallet pickup for tomorrow period new line the hand roll towels are running low comma we need another box period new line cheers comma Dave period"
- Release. Text appears.
- Stop recording

**SEGMENT 3: DICTATION MODES + PER-APP (3-4 min)**
- Start recording
- Press F7 — toast shows "Mode: Prose"
- Press F7 — toast shows "Mode: Code"
- Press F7 — toast shows "Mode: Email"
- Press F7 — toast shows "Mode: Auto"
- Now switch to Terminal. Hold Right Ctrl, dictate: "ls dash la slash warehouse slash stock"
- Switch to Discord. Dictate: "yeah mate all good see you tomorrow"
- Switch to email. Dictate: "Dear client please find attached the invoice for this week"
- Stop recording

**SEGMENT 4: VOICE COMMANDS (3-4 min)**
- Start recording
- Open WordPad. Dictate a paragraph: "The quick brown fox jumps over the lazy dog period the lazy dog did not appreciate being jumped over period"
- Now demonstrate each command as a separate dictation:
  - Hold Ctrl, say "scratch that", release — text deleted
  - Dictate the paragraph again
  - "delete last word" — last word gone
  - "delete last three words" — three words gone
  - "delete last sentence" — sentence gone
  - "capitalize that" — re-injected with caps
  - "bold that" — **bold**
  - "replace fox with cat" — swapped
  - "redo verbatim" — raw words back
- Stop recording

**SEGMENT 5: HOTKEYS (1 min)**
- Start recording
- Press F8 — toast "copied last dictation"
- Open another window, Ctrl+V — text pastes
- Press F6 — text deleted, recording starts immediately. Say something. Release.
- Press Pause key while recording — toast "paused". Press again — "resumed".
- Stop recording

**SEGMENT 6: VISUALIZER + SETTINGS + MIC TEST (1-2 min)**
- Start recording
- Right-click tray icon -> Settings
- Show the Visualizer dropdown, switch between Equalizer and Blob
- Hold Right Ctrl and talk briefly to show the blob/equalizer reacting
- Click "Record 3s & transcribe" — speak, show result
- Show the WPM stat in the tray menu
- Stop recording

**SEGMENT 7: PRIVACY PROOF (30 sec)**
- Start recording
- Open Task Manager (Ctrl+Shift+Esc) -> Performance tab -> Wi-Fi (show it's off / no traffic)
- Or open Resource Monitor -> Network tab (show zero connections)
- Right-click tray -> How to use (show the guide briefly)
- Stop recording

**SEGMENT 8: INSTALL (optional, 1 min)**
- Start recording
- Show the installer file on desktop
- Double-click, show SmartScreen warning, click "More info" -> "Run anyway"
- Show installer progress (you can speed this up in editing)
- Stop recording
- NOTE: Only include this if the video feels too short without it. Most viewers want to see the app working, not installing.

---

## STEP 5: RECORD THE VOICEOVER (30 minutes)

Now you add your voice explaining what's happening. You have two options:

### OPTION A: Live voiceover (easier, less polished)
- Open the screen recordings in CapCut
- Talk over them, explaining what's happening
- If you stumble, just pause and re-say the sentence, then cut the bad bit in editing

### OPTION B: Post-recorded voiceover (more polished, recommended)
- Open each screen recording video file
- Play it and read from the script below
- Record your voice separately (you can use Windows Voice Recorder, or Audacity, or just record in CapCut directly)
- Sync the audio to the video in CapCut

### The voiceover script (what to say, segment by segment):

**SEGMENT 1 (Hook):**
"This is Dictate. It runs entirely on my PC — no cloud, no subscription. Watch. I turn off my Wi-Fi... and it still works perfectly. Your voice never leaves your machine."

**SEGMENT 2 (Push-to-talk):**
"I hold Right Ctrl and just talk. I say 'comma' for a comma, 'period' for a full stop, 'new line' to start a new line. Let go, and the text appears — clean, punctuated, no filler words. The 'um' and 'uh' get stripped automatically."

**SEGMENT 3 (Modes + profiles):**
"Press F7 to switch modes — Prose, Code, Email, Auto. But the smart part is per-app detection. In a terminal, I get verbatim — no capitals, no cleanup. In Discord, casual. In an email, professional. Same words, different formatting, all automatic. This is the feature Superwhisper charges two hundred and fifty dollars for."

**SEGMENT 4 (Voice commands):**
"This is what makes it a tool, not a toy. 'Scratch that' deletes everything. 'Delete last word' removes one word. 'Delete last sentence' wipes from the last period. 'Capitalize that' fixes the casing. 'Bold that' wraps it in markdown. 'Replace fox with cat' — find and replace, by voice. 'Redo verbatim' puts the raw words back if the cleanup was too aggressive."

**SEGMENT 5 (Hotkeys):**
"Three rescue buttons. F8 copies your last dictation — for when text lands in the wrong window. F6 deletes the last dictation and instantly re-records — one button rescue. Pause key freezes mid-recording."

**SEGMENT 6 (Visualizer + settings):**
"Settings has everything. Pick your visualizer — clean equalizer bars, or a blob that changes colour with your volume. Test your mic right here — record three seconds, see the transcription. And the tray shows your words per minute."

**SEGMENT 7 (Privacy):**
"Zero network connections. Your voice is processed in RAM and thrown away. Nothing is uploaded, ever. It's open source — you can read every line of code."

**SEGMENT 8 (Install — if included):**
"Download the installer, run it. Windows shows a warning because it's not code-signed — that's normal for free open-source apps. Click 'More info', 'Run anyway'. It installs to your user folder, no admin password needed."

**OUTRO:**
"Download link and source code in the description. It's free, open source, and works offline. If you found this useful, hit like — it helps other people find it. Subscribe for more."

---

## STEP 6: EDIT IN CAPCUT (30-60 minutes)

1. Open CapCut
2. Import all your recording segments (drag and drop the MP4 files)
3. Drag them onto the timeline in order
4. If you did post-recorded voiceover, import the audio file and drag it under the video

### Basic editing steps:

**Cut dead air:**
- Click on the video clip where there's silence (you holding the key before speaking)
- Click the **Split** button (or press Ctrl+B) to cut the clip
- Delete the silent part
- This makes the video feel faster and more professional

**Add text overlays:**
- Click **Text** in the top menu
- Add a text box for each section title (e.g., "Push-to-Talk Demo", "Voice Commands")
- Place the text at the start of each segment
- Use a clean font (Inter, Roboto, or Arial), white text, slight shadow

**Zoom in on toasts:**
- When a toast appears (word count, mode change), the text is small
- Use CapCut's **zoom** feature: click the clip, go to **Video** -> **Scale**, increase to 150-200%
- Position the zoom so the toast fills the frame
- Add a keyframe at the start and end of the zoom so it smoothly zooms in and out

**Speed up boring parts:**
- The install segment can be sped up: right-click the clip -> **Speed** -> **2x** or **4x**
- The model download progress bar can be sped up too

**Add background music (optional):**
- CapCut has free music in the **Audio** tab
- Pick something calm and low-volume (lo-fi, ambient)
- Set the volume to 10-15% so it doesn't compete with your voice

**Export:**
- Click **Export** (top right)
- Set resolution to 1080p
- Set frame rate to 30
- Set quality to High
- Export as MP4

---

## STEP 7: THUMBNAIL (10 minutes)

You need a thumbnail that makes people click. Keep it simple:

### English thumbnail:
1. Take a screenshot of the blob visualizer while you're talking (it looks cool)
2. Open it in any image editor (even MS Paint)
3. Add text at the top: **"FREE DICTATION"** (big, bold, white with black outline)
4. Add text at the bottom: **"100% OFFLINE"**
5. Add a small red circle with a line through it over a "$15/mo" text (to show it's free)
6. Save as PNG

### Bosnian thumbnail:
1. Same blob screenshot
2. Top text: **"BESPLATNO DIKTIRANJE"**
3. Bottom text: **"BEZ INTERNETA"**
4. Save as PNG

### Even easier option:
Use Canva (canva.com, free). Search "YouTube thumbnail template". Add your screenshot and text. Download. Done.

---

## STEP 8: UPLOAD TO YOUTUBE (15 minutes)

1. Go to youtube.com/upload
2. Drag and drop your MP4 file
3. Title (English): "FREE Offline Dictation App — Better Than Wispr Flow ($0 vs $15/mo)"
4. Title (Bosnian): "Besplatno diktiranje na bosanskom jeziku — bez interneta"
5. Description — copy from the script guide (the description templates are in the youtube-video-guide.md file)
6. Tags (English): whisper, dictation, speech to text, free, offline, windows, wispr flow alternative, superwhisper alternative, voice typing, ai dictation
7. Tags (Bosnian): bosanski jezik, diktiranje, whisper, diktafon, govor u tekst, besplatno, bez interneta, speech to text bosnian
8. Thumbnail — upload your PNG
9. Set visibility to **Public**
10. Publish

### Add chapters (put these in the description):
```
0:00 - Wi-Fi Off Demo
0:20 - What is Dictate?
1:00 - Install & Setup
2:00 - Push-to-Talk Demo
3:30 - Dictation Modes & Per-App Profiles
4:30 - Voice Commands
6:00 - Hotkeys (F6, F8, Pause)
6:30 - Visualizer & Settings
7:30 - Privacy Proof
8:00 - Download & Outro
```

---

## STEP 9: FOR THE BOSNIAN VIDEO

Everything is the same EXCEPT:

1. Set Dictate's language to Bosnian in Settings before recording
2. Dictate in Bosnian for all segments
3. Use Bosnian punctuation commands: "tačka", "zarez", "upitnik", "uzvičnik", "novi red", "novi pasus"
4. Use Bosnian voice commands: "obriši to", "obriši posljednju riječ", "obriši posljednju rečenicu", "podebljaj", "iskosi", "zamijeni X sa Y"
5. Dictate a paragraph with poštapalice to show filler removal: "E, ono, znači, idemo u grad"
6. Voiceover in Bosnian — use the Bosnian script from the youtube-video-guide.md file
7. Title and description in Bosnian
8. Tags in Bosnian

The Bosnian video can be shorter (8 min) since you don't need to show as many features — focus on: offline, Bosnian punctuation, Bosnian voice commands, filler removal, and the Wi-Fi-off moment. Those are the things that will make Bosnian speakers share it.

---

## TROUBLESHOOTING

**OBS isn't capturing audio:**
- Settings -> Audio -> make sure "Desktop Audio" is set to "Default" and "Mic/Aux" is set to your microphone
- Check Windows sound settings — make sure the right mic is set as default

**The recording is laggy:**
- Settings -> Output -> Output Mode -> Simple -> Recording Quality -> High Quality, Medium File Size
- Close Chrome and other heavy apps while recording
- Lower the FPS to 24 if 30 is too much

**Dictate text isn't showing in the recording:**
- The overlay is a separate always-on-top window — OBS should capture it with Display Capture
- If it doesn't, try Window Capture instead of Display Capture (but Display Capture should work)

**Your voice sounds bad:**
- Don't use the laptop built-in mic — use a headset, earbuds with mic, or a USB mic
- Record in a quiet room with the door closed
- In CapCut, you can add a "noise reduction" effect to your audio track

**CapCut keeps crashing:**
- Make sure you have enough disk space (videos are large)
- Close other apps while editing
- Export in segments if the video is long

---

## TIMELINE SUMMARY

| Step | Time | What |
|------|------|------|
| Install OBS + CapCut | 10 min | One-time setup |
| Set up OBS | 5 min | One-time setup |
| Prepare screen | 5 min | Before each recording session |
| Record segments | 30-45 min | 8 short recordings |
| Record voiceover | 30 min | Read the script while watching playback |
| Edit in CapCut | 30-60 min | Cut dead air, add text, zoom on toasts |
| Make thumbnail | 10 min | Screenshot + text overlay |
| Upload to YouTube | 15 min | Title, description, tags, thumbnail |
| **Total** | **~3 hours** | For a polished 8-10 minute video |

You don't have to do it all in one sitting. Record one day, edit the next. The segments are independent so you can redo any one without affecting the others.

---

## THE ONE THING THAT MATTERS MOST

If you only do one thing well, make it the Wi-Fi-off moment. That's the 20-second clip that people will share. Practice it 5 times before recording. It needs to be smooth: start dictating, turn off Wi-Fi without stopping, keep dictating, text still appears. That's the clip that goes on Shorts/TikTok/reddit and gets people to watch the full video.

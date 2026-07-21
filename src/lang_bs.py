"""Bosnian (bs/hr/sr) voice pack: punctuation phrases, edit commands,
hesitation fillers, silence hallucinations and the Whisper anchor prompt.

Single source of truth so every Bosnian-facing behaviour lives in one file.
Ijekavian orthography throughout. ASCII fallbacks are included for phrases
where Whisper sometimes drops diacritics ("tacka" for "tačka").
"""

# Spoken phrase -> replacement. Merged into the engine lexicon when the
# configured language is bs/hr/sr or auto. Sorted longest-first at merge
# time, so multi-word phrases always win over their single-word prefixes.
PUNCTUATION = [
    ("tačka-zarez", ";"), ("tacka-zarez", ";"),
    ("znak pitanja", "?"),
    ("novi red", "\n"),
    ("novi pasus", "\n\n"),
    ("otvorena zagrada", "("), ("zatvorena zagrada", ")"),
    ("trotačka", "…"), ("trotacka", "…"),
    ("tačka", "."), ("tacka", "."),
    ("zarez", ","),
    ("upitnik", "?"),
    ("uzvičnik", "!"), ("uzvicnik", "!"),
    ("dvotačka", ":"), ("dvotacka", ":"),
    ("navodnici", '"'),
    ("crta", "—"),
]

# Pure hesitation sounds only. Real words like "pa", "ma", "znači" must
# NEVER appear here (stripping them mangles normal sentences).
FILLERS = ["ovaj", "hm", "hmm", "mhm", "aha", "eee"]

# Whole-utterance phrases Whisper hallucinates on silent bs/hr/sr audio.
# Compared after ASCII-folding, so keep these diacritic-free.
HALLUCINATIONS = frozenset({
    "hvala", "hvala.", "hvala vam", "hvala na gledanju",
    "hvala na gledanju.", "hvala vam na gledanju",
    "pretplatite se", "prijavite se", "prijavite se na kanal",
})

# initial_prompt anchor: nudges Whisper toward ijekavian Bosnian with
# proper diacritics instead of drifting into Serbian ekavian or ASCII.
# Used only when the user has not set their own initial_prompt.
ANCHOR_PROMPT = ("Zdravo, ovo je diktat na bosanskom jeziku. "
                 "Riječi poput lijepo, mlijeko i vrijeme pišu se ijekavicom.")

# (normalized utterance, command kind, kwargs) — consumed by
# voice_commands.parse(). Utterances are matched after _norm(), which
# lowercases and strips punctuation but PRESERVES š č ć đ ž.
COMMANDS = [
    ("obriši to", "scratch", {}), ("obrisi to", "scratch", {}),
    ("poništi to", "scratch", {}), ("ponisti to", "scratch", {}),
    ("poništi", "scratch", {}),
    ("obriši posljednju riječ", "delete_words", {"n": 1}),
    ("obrisi posljednju rijec", "delete_words", {"n": 1}),
    ("obriši riječ", "delete_words", {"n": 1}),
    ("obriši posljednje dvije riječi", "delete_words", {"n": 2}),
    ("obriši posljednje tri riječi", "delete_words", {"n": 3}),
    ("obriši posljednju rečenicu", "delete_sentence", {}),
    ("obrisi posljednju recenicu", "delete_sentence", {}),
    ("obriši rečenicu", "delete_sentence", {}),
    ("podebljaj", "format", {"mode": "bold"}),
    ("podebljaj to", "format", {"mode": "bold"}),
    ("iskosi", "format", {"mode": "italic"}),
    ("iskosi to", "format", {"mode": "italic"}),
    ("kurziv", "format", {"mode": "italic"}),
    ("označi sve", "format", {"mode": "select_all"}),
    ("oznaci sve", "format", {"mode": "select_all"}),
    ("velika slova", "recase", {"mode": "upper"}),
    ("mala slova", "recase", {"mode": "lower"}),
    ("ponovi doslovno", "redo_verbatim", {}),
]

LANGS = ("bs", "hr", "sr")


def is_bs_family(language: str | None) -> bool:
    return (language or "").lower() in LANGS

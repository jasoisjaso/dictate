"""Offscreen boot smoke: construct the REAL DictationTrayApp (no mocks),
wait for the model to actually load, then poke the coordinator surfaces the
unit suite can't reach — tray rendering, mode cycling, hotkey controller,
the delivery delegates — and quit cleanly.

Run on Windows:  .venv-win\\Scripts\\python.exe tests\\smoke_boot.py

Uses QT_QPA_PLATFORM=offscreen and skips main.py's single-instance lock, so
it is safe to run while a normal Dictate instance is already in the tray.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

READY_DEADLINE_S = 120  # first run may still need a model download


def main():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from src import config as config_mod
    from src.app_states import IDLE, LOADING, RECORDING, TRANSCRIBING
    from src.ui import DictationTrayApp

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cfg = config_mod.load()
    # DICTATE_SMOKE_ENGINE=parakeet|whisper|auto forces the engine so the
    # same smoke can prove BOTH engines boot the full app on this machine.
    forced = os.environ.get("DICTATE_SMOKE_ENGINE")
    if forced:
        cfg.setdefault("engine", {})["engine"] = forced
    if forced == "parakeet":
        # The machine's real settings may sit on a Whisper-only mode (bs,
        # bs2en, multi...) and the router would then honestly fall back —
        # that honesty is unit-tested in test_parakeet_engine.py. THIS smoke
        # asks a different question ("does Parakeet boot the whole app?"),
        # so pin a language Parakeet supports.
        cfg.setdefault("whisper", {})["language"] = "en"
    tray_app = DictationTrayApp(cfg, app)

    n = 0

    def ok(name, cond):
        nonlocal n
        assert cond, f"FAIL: {name}"
        n += 1
        print(f"[{n}] {name} OK")

    ok("constructed in LOADING state", tray_app.state == LOADING)
    ok("hotkey listener running", tray_app.hotkeys._listener is not None)
    ok("trigger hint is text", len(tray_app._trigger_hint()) > 0)

    waited = {"s": 0.0}

    def poll_ready():
        if tray_app.state == IDLE:
            run_checks()
            return
        waited["s"] += 0.5
        if waited["s"] > READY_DEADLINE_S:
            print(f"FAIL: model not ready after {READY_DEADLINE_S}s "
                  f"(state={tray_app.state})")
            app.exit(2)
            return
        QTimer.singleShot(500, poll_ready)

    def run_checks():
        try:
            _run_checks_inner()
        except Exception as ex:
            # An assert inside a Qt timer callback only prints — the event
            # loop keeps running and the smoke HANGS. Exit loudly instead.
            print(ex)
            app.exit(3)
            return
        tray_app._quit()

    def _run_checks_inner():
        ok("booted to IDLE (model loaded)", tray_app.state == IDLE)
        ok("engine reports a device", bool(tray_app.engine.active_device))
        ok("engine identifies itself",
           getattr(tray_app.engine, "engine_name", "") in
           ("whisper", "parakeet"))
        if forced in ("whisper", "parakeet"):
            ok(f"forced engine honoured ({forced})",
               tray_app.engine.engine_name == forced)
        ok("engine note is settled",
           hasattr(tray_app.engine, "engine_note"))

        # mode cycle: full loop lands back on auto and updates the menu label
        for _ in range(4):
            tray_app._cycle_mode()
        ok("mode cycle loops back to auto", tray_app._dict_mode == "auto")

        # tray rendering for every state must not raise
        for st in (RECORDING, TRANSCRIBING, IDLE):
            tray_app._set_state(st)
        ok("tray renders all states", tray_app.state == IDLE)

        # delivery delegates: one shared copy of the bookkeeping
        tray_app.last_raw_text = "smoke raw"
        tray_app.last_injected_text = "smoke injected "
        tray_app.last_injected_len = len("smoke injected ")
        ok("last_raw_text delegates to delivery",
           tray_app.delivery.last_raw_text == "smoke raw")
        ok("last_injected delegates to delivery",
           tray_app.delivery.last_injected_len == 15)

        # stats label formats without raising
        tray_app._session_words = 42
        tray_app._update_stats_label()
        ok("stats label updates", "42" in tray_app.shell.act_stats.text())

    QTimer.singleShot(500, poll_ready)
    rc = app.exec()
    if rc == 0:
        print(f"smoke_boot: all {n} checks passed")
    sys.exit(rc)


if __name__ == "__main__":
    main()

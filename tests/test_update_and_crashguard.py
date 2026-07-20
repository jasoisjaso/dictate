"""Tests for update_check (version compare, throttling) and crashguard
(crash detection, CPU fallback decision)."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import crashguard
import update_check


# ---- version parsing / comparison ------------------------------------------

def test_parse_version_variants():
    assert update_check.parse_version("v1.2.1") == (1, 2, 1)
    assert update_check.parse_version("1.2.1") == (1, 2, 1)
    assert update_check.parse_version("v2.0") == (2, 0)
    assert update_check.parse_version("garbage") is None
    assert update_check.parse_version("") is None


def test_is_newer():
    assert update_check.is_newer("v1.2.1", "1.2.0")
    assert update_check.is_newer("v2.0", "1.9.9")
    assert not update_check.is_newer("v1.2.0", "1.2.0")
    assert not update_check.is_newer("v1.1.9", "1.2.0")
    # padding: 1.3 > 1.2.1
    assert update_check.is_newer("v1.3", "1.2.1")
    # garbage tags never claim to be newer
    assert not update_check.is_newer("weird-tag", "1.2.0")


def test_throttle_respects_recent_check(tmp_path):
    state = tmp_path / update_check.STATE_FILE
    state.write_text(json.dumps({"last_check": time.time()}))
    assert update_check._throttled(str(state), min_interval_h=20)
    # stale check -> not throttled
    state.write_text(json.dumps({"last_check": time.time() - 999999}))
    assert not update_check._throttled(str(state), min_interval_h=20)
    # missing/corrupt file -> not throttled
    assert not update_check._throttled(str(tmp_path / "nope.json"), 20)


def test_check_github_fail_silent(tmp_path, monkeypatch):
    # network exploding must return None, never raise
    import urllib.request

    def boom(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert update_check.check_github("x/y", "1.0.0",
                                     state_dir=str(tmp_path)) is None


# ---- crashguard decision logic ----------------------------------------------

def test_first_run_is_not_a_crash():
    crashed, consecutive = crashguard.assess(500, {})
    assert crashed is False
    assert consecutive == 0


def test_grown_crash_log_means_crash():
    crashed, consecutive = crashguard.assess(
        900, {"crash_log_size": 500, "consecutive_crashes": 0})
    assert crashed is True
    assert consecutive == 1


def test_consecutive_crashes_accumulate():
    crashed, consecutive = crashguard.assess(
        1200, {"crash_log_size": 900, "consecutive_crashes": 1})
    assert crashed and consecutive == 2


def test_clean_run_resets_counter():
    crashed, consecutive = crashguard.assess(
        900, {"crash_log_size": 900, "consecutive_crashes": 3})
    assert not crashed and consecutive == 0


def test_truncated_log_rebaselines_without_crash():
    crashed, _ = crashguard.assess(0, {"crash_log_size": 900})
    assert crashed is False


def test_force_cpu_only_after_two_cuda_crashes():
    assert crashguard.should_force_cpu(2, "cuda")
    assert crashguard.should_force_cpu(3, "cuda")
    assert not crashguard.should_force_cpu(1, "cuda")
    assert not crashguard.should_force_cpu(2, "cpu")
    assert not crashguard.should_force_cpu(2, None)


# ---- startup_check end-to-end -----------------------------------------------

def test_startup_check_flow(tmp_path):
    appdata = str(tmp_path)
    crash_log = os.path.join(appdata, "crash.log")

    # run 1: no crash.log at all
    r1 = crashguard.startup_check(appdata, crash_log)
    assert r1["crashed"] is False and r1["force_cpu"] is False

    # simulate a CUDA session that crashed (crash.log appears/grows)
    crashguard.record_device(appdata, "cuda")
    with open(crash_log, "w") as f:
        f.write("Windows fatal exception: access violation\n" * 10)

    r2 = crashguard.startup_check(appdata, crash_log)
    assert r2["crashed"] is True and r2["force_cpu"] is False
    assert "crashed last time" in r2["note"]

    # crash again -> force CPU
    crashguard.record_device(appdata, "cuda")
    with open(crash_log, "a") as f:
        f.write("another crash\n" * 10)
    r3 = crashguard.startup_check(appdata, crash_log)
    assert r3["crashed"] is True and r3["force_cpu"] is True
    assert "CPU" in r3["note"]

    # clean run afterwards -> everything resets
    crashguard.record_device(appdata, "cpu")
    r4 = crashguard.startup_check(appdata, crash_log)
    assert r4["crashed"] is False and r4["force_cpu"] is False


def test_corrupt_state_file_never_crashes(tmp_path):
    p = crashguard.state_path(str(tmp_path))
    with open(p, "w") as f:
        f.write("{not json!!!")
    assert crashguard.read_state(p) == {}
    r = crashguard.startup_check(str(tmp_path),
                                 os.path.join(str(tmp_path), "crash.log"))
    assert r["force_cpu"] is False

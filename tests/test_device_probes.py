"""Ticket 10: the hardware probes tell the truth, and ask nothing impossible.

On macOS the Tier answer was already right, but by accident: `nvidia-smi` and
`wmic` are simply absent, so both probes returned their failure value. That is
a coincidence, not a decision — and it means the app shells out looking for
tools that cannot exist on an Apple Silicon Mac.

The seams are pure: `system` is an argument, so the macOS decision is testable
from Windows and the Windows one from here. `tier_reason` is the sentence the
tray and the log show, so "cpu" stops being unexplained.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import device  # noqa: E402


# ---- no impossible probes ---------------------------------------------------

def test_no_nvidia_probe_on_macos():
    assert device.wants_nvidia_probe("Darwin") is False


def test_no_amd_wmic_probe_on_macos():
    assert device.wants_amd_probe("Darwin") is False


def test_windows_still_probes_both():
    assert device.wants_nvidia_probe("Windows") is True
    assert device.wants_amd_probe("Windows") is True


def test_linux_probes_nvidia_but_not_wmic():
    """CUDA on Linux is real; wmic is a Windows-only binary."""
    assert device.wants_nvidia_probe("Linux") is True
    assert device.wants_amd_probe("Linux") is False


def test_amd_probe_short_circuits_on_macos_without_running_anything():
    """The point of the ticket: not 'returns False', but 'never shells out'."""
    def explode(*a, **k):
        raise AssertionError("no subprocess may run on macOS")

    assert device._amd_gpu_present(system="Darwin", _which=explode) is False


def test_vram_probe_short_circuits_on_macos_without_running_anything():
    def explode(*a, **k):
        raise AssertionError("no subprocess may run on macOS")

    assert device._vram_gb(system="Darwin", _which=explode) == 0.0


def test_windows_amd_probe_still_runs_its_lookup():
    seen = []
    assert device._amd_gpu_present(system="Windows",
                                   _which=lambda n: seen.append(n)) is False
    assert seen == ["wmic"]


# ---- the tray gets something truthful to show -------------------------------

def test_apple_silicon_cpu_tier_says_so():
    tier = device.choose_tier(cuda=False, vram_gb=0.0)
    reason = device.tier_reason(tier, system="Darwin", machine="arm64")
    assert "Apple Silicon" in reason
    assert "CPU" in reason


def test_intel_mac_is_not_called_apple_silicon():
    tier = device.choose_tier(cuda=False, vram_gb=0.0)
    reason = device.tier_reason(tier, system="Darwin", machine="x86_64")
    assert "Apple Silicon" not in reason


def test_cuda_tier_reason_names_the_gpu_path():
    tier = device.choose_tier(cuda=True, vram_gb=16.0)
    reason = device.tier_reason(tier, system="Windows", machine="AMD64")
    assert "GPU" in reason or "CUDA" in reason


def test_amd_tier_reason_explains_the_cpu_fallback():
    tier = device.choose_tier(cuda=False, vram_gb=0.0)
    tier.amd_gpu = True
    reason = device.tier_reason(tier, system="Windows", machine="AMD64")
    assert "AMD" in reason


def test_windows_cpu_reason_is_not_a_mac_sentence():
    tier = device.choose_tier(cuda=False, vram_gb=0.0)
    reason = device.tier_reason(tier, system="Windows", machine="AMD64")
    assert "Apple" not in reason
    assert reason


def test_reason_is_always_a_non_empty_sentence():
    for system, machine in (("Darwin", "arm64"), ("Windows", "AMD64"),
                            ("Linux", "x86_64"), ("Haiku", "sparc")):
        tier = device.choose_tier(cuda=False, vram_gb=0.0)
        assert device.tier_reason(tier, system=system, machine=machine).strip()

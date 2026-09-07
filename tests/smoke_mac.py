"""Mac port smoke probe: does every dependency the port needs actually work here?

Not a unit test — a fact-finder run once per machine while scoping the port.
Prints one line per capability so a failure names itself.
"""
import platform
import sys

print(f"python  {sys.version.split()[0]}  {platform.machine()}  macOS {platform.mac_ver()[0]}")

try:
    import ctranslate2
    print(f"ctranslate2 {ctranslate2.__version__}  cuda_devices={ctranslate2.get_cuda_device_count()}")
except Exception as ex:
    print(f"ctranslate2 FAILED: {ex}")

try:
    import faster_whisper
    print(f"faster_whisper {faster_whisper.__version__}")
except Exception as ex:
    print(f"faster_whisper FAILED: {ex}")

try:
    import sherpa_onnx
    print(f"sherpa_onnx {sherpa_onnx.__version__ if hasattr(sherpa_onnx, '__version__') else 'ok'}")
except Exception as ex:
    print(f"sherpa_onnx FAILED: {ex}")

try:
    import sounddevice as sd
    ins = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    print(f"sounddevice ok  inputs={ins}  default_in={sd.default.device[0]}")
except Exception as ex:
    print(f"sounddevice FAILED: {ex}")

try:
    from pynput import keyboard
    print(f"pynput ok  ctrl_r={keyboard.Key.ctrl_r}")
except Exception as ex:
    print(f"pynput FAILED: {ex}")

try:
    from PySide6 import QtCore
    print(f"PySide6 {QtCore.__version__}")
except Exception as ex:
    print(f"PySide6 FAILED: {ex}")

try:
    import Quartz
    # The two Quartz calls the mac injection backend would be built on.
    assert Quartz.CGEventCreateKeyboardEvent
    assert Quartz.CGEventKeyboardSetUnicodeString
    trusted = Quartz.CGPreflightListenEventAccess() if hasattr(
        Quartz, "CGPreflightListenEventAccess") else None
    print(f"Quartz ok  CGEvent unicode api present  listen_access={trusted}")
except Exception as ex:
    print(f"Quartz FAILED: {ex}")

try:
    from AppKit import NSWorkspace
    front = NSWorkspace.sharedWorkspace().frontmostApplication()
    print(f"AppKit ok  frontmost={front.localizedName() if front else None}")
except Exception as ex:
    print(f"AppKit FAILED: {ex}")

# The pure-logic modules that should already be portable, imported with no
# Windows shim in the way.
sys.path.insert(0, "src")
for mod in ("device", "config", "transforms", "auto_punct", "paths"):
    try:
        __import__(mod)
        print(f"src/{mod}.py imports clean")
    except Exception as ex:
        print(f"src/{mod}.py FAILED: {type(ex).__name__}: {ex}")

try:
    import device
    print(f"device.detect() -> {device.detect().as_dict()}")
    print(f"device.choose_engine('auto', cpu_tier, 'en') -> "
          f"{device.choose_engine('auto', device.detect(), 'en')}")
except Exception as ex:
    print(f"device routing FAILED: {type(ex).__name__}: {ex}")

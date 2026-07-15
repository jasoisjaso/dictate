import sys
sys.path.insert(0, 'src')
try:
    from settings_gui import SettingsDialog
    print("SettingsDialog imported OK")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()

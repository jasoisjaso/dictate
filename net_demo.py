# Quick network kill/restore for the YouTube demo.
# Usage:
#   python net_demo.py off   — disable all network adapters (kills internet)
#   python net_demo.py on    — re-enable all network adapters
#   python net_demo.py check — show current status
#
# This does NOT require admin if you run it from an admin PowerShell.
# For the video: open an admin PowerShell window before recording,
# then just type the commands during the demo.

import subprocess
import sys

def get_adapters():
    """Return list of active network adapter names."""
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n")
    adapters = []
    for line in lines[3:]:  # skip header lines
        parts = line.split()
        if len(parts) >= 4:
            state = parts[0]
            name = " ".join(parts[3:])
            if state == "Connected":
                adapters.append(name)
    return adapters

def disable_all():
    adapters = get_adapters()
    if not adapters:
        print("No active adapters found.")
        return
    for name in adapters:
        subprocess.run(
            ["netsh", "interface", "set", "interface", name, "admin=disable"],
            capture_output=True
        )
        print(f"  DISABLED: {name}")
    print("\n*** INTERNET IS OFF ***")

def enable_all():
    # Get ALL adapters (including disabled ones)
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n")
    for line in lines[3:]:
        parts = line.split()
        if len(parts) >= 4:
            name = " ".join(parts[3:])
            subprocess.run(
                ["netsh", "interface", "set", "interface", name, "admin=enable"],
                capture_output=True
            )
            print(f"  ENABLED: {name}")
    print("\n*** INTERNET IS BACK ***")

def check():
    adapters = get_adapters()
    if adapters:
        print("Active adapters:")
        for a in adapters:
            print(f"  - {a}")
        print("\nStatus: CONNECTED (internet is ON)")
    else:
        print("No active adapters.")
        print("\nStatus: DISCONNECTED (internet is OFF)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "off":
        disable_all()
    elif cmd == "on":
        enable_all()
    elif cmd == "check":
        check()
    else:
        print("Usage: python net_demo.py [off|on|check]")

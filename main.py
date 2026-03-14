#!/usr/bin/env python3
"""
Bop-It SPIKE Prime — Linux entry point.

Usage:
    python main.py

Serial port is auto-detected. Override with:
    BOPIT_SERIAL_PORT=/dev/ttyACM0 python main.py
"""

import re
import sys
import subprocess
import threading
import time
import tkinter as tk

from boppit import serial_interface
from boppit.hub_code import HUB_CODE
from boppit.game import BopItGame


def _inhibit_screensaver() -> str | None:
    """Prevent display blanking while the game runs.

    Tries the freedesktop D-Bus ScreenSaver.Inhibit call first (works on KDE /
    Steam Deck desktop mode).  If that fails, starts a background thread that
    calls `xset s reset` every 30 s instead.

    Returns the D-Bus cookie string if inhibit succeeded, else None.
    """
    try:
        result = subprocess.run(
            [
                "dbus-send", "--session", "--print-reply",
                "--dest=org.freedesktop.ScreenSaver",
                "/org/freedesktop/ScreenSaver",
                "org.freedesktop.ScreenSaver.Inhibit",
                "string:BopIt", "string:Game in progress",
            ],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            match = re.search(r"uint32 (\d+)", result.stdout)
            if match:
                cookie = match.group(1)
                print(f"[Screen] Screensaver inhibited via D-Bus (cookie {cookie})")
                return cookie
    except Exception:
        pass

    # Fallback: periodically reset the X screensaver idle timer
    print("[Screen] D-Bus inhibit unavailable — using xset fallback")
    def _reset_loop():
        while True:
            time.sleep(30)
            try:
                subprocess.run(["xset", "s", "reset"],
                               capture_output=True, timeout=2)
            except Exception:
                pass
    threading.Thread(target=_reset_loop, daemon=True).start()
    return None


def _uninhibit_screensaver(cookie: str | None) -> None:
    if cookie is None:
        return
    try:
        subprocess.run(
            [
                "dbus-send", "--session",
                "--dest=org.freedesktop.ScreenSaver",
                "/org/freedesktop/ScreenSaver",
                "org.freedesktop.ScreenSaver.UnInhibit",
                f"uint32:{cookie}",
            ],
            capture_output=True, timeout=3,
        )
        print("[Screen] Screensaver inhibit released")
    except Exception:
        pass


def main():
    ser = None
    cookie = _inhibit_screensaver()
    try:
        ser = serial_interface.connect()
        if not serial_interface.check_hub_ready(ser):
            serial_interface.upload_hub_code(ser, HUB_CODE)

        root = tk.Tk()
        game = BopItGame(root, ser)
        root.mainloop()

    except RuntimeError as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        _uninhibit_screensaver(cookie)
        if ser and ser.is_open:
            ser.close()
            print("[Serial] Port closed.")


if __name__ == "__main__":
    main()

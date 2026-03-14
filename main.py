#!/usr/bin/env python3
"""
Bop-It SPIKE Prime — Linux entry point.

Usage:
    python main.py

Serial port is auto-detected. Override with:
    BOPIT_SERIAL_PORT=/dev/ttyACM0 python main.py
"""

import sys
import tkinter as tk

from boppit import serial_interface
from boppit.hub_code import HUB_CODE
from boppit.game import BopItGame


def main():
    ser = None
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
        if ser and ser.is_open:
            ser.close()
            print("[Serial] Port closed.")


if __name__ == "__main__":
    main()

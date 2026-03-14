#!/usr/bin/env python3
"""
SPIKE Prime serial diagnostic.
Usage:
    python3 test_serial.py              # auto-detect
    python3 test_serial.py /dev/ttyACM0
    python3 test_serial.py /dev/ttyACM0 /dev/ttyACM1   # test two ports simultaneously
"""
import sys
import time
import threading
import serial
import serial.tools.list_ports


TEST_CODE = 'print("DIAG:HELLO")\n'


def read_port(ser, label, duration=6):
    """Read from ser for `duration` seconds, printing everything."""
    end = time.time() + duration
    buf = b""
    while time.time() < end:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            # print each complete line
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                print(f"  [{label}] << {repr(line.decode('utf-8', errors='replace').strip())}")
    if buf.strip():
        print(f"  [{label}] << (partial) {repr(buf)}")


def test_port(port):
    print(f"\n{'='*50}")
    print(f"Testing: {port}")
    print(f"{'='*50}")

    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        print(f"  FAILED to open: {e}")
        return

    time.sleep(1)

    print("  Sending Ctrl-C x2 (interrupt)...")
    ser.write(b"\x03\x03")
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting)
    if resp:
        print(f"  After interrupt: {repr(resp)}")

    print("  Sending Ctrl-E (paste mode)...")
    ser.write(b"\x05")
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting)
    if resp:
        print(f"  After paste mode: {repr(resp)}")
    else:
        print("  (no response to paste mode)")

    print(f"  Sending test code: {repr(TEST_CODE)}")
    ser.write(TEST_CODE.encode("utf-8"))
    time.sleep(0.2)

    print("  Sending Ctrl-D (execute)...")
    ser.write(b"\x04")

    print("  Reading for 6 seconds (perform an action on the hub)...")
    read_port(ser, port, duration=6)

    ser.close()
    print(f"  Done: {port}")


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device:20s}  {p.description}")
    return ports


if __name__ == "__main__":
    ports = list_ports()

    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        # Auto-select all ttyACM devices
        targets = [p.device for p in ports if "ttyACM" in p.device or "ttyUSB" in p.device]
        if not targets and ports:
            targets = [ports[0].device]

    if not targets:
        print("\nNo ports found. Is the hub plugged in?")
        sys.exit(1)

    print(f"\nWill test: {targets}")

    if len(targets) == 1:
        test_port(targets[0])
    else:
        # Test all ports simultaneously in threads
        threads = [threading.Thread(target=test_port, args=(p,)) for p in targets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    print("\nDiagnostic complete.")
    print("\nIf you saw DIAG:HELLO from a port, that is the correct port to use.")
    print("Set it with:  BOPIT_SERIAL_PORT=/dev/ttyACMx python3 main.py")

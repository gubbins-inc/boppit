import os
import time
import serial
import serial.tools.list_ports

from .config import BAUD_RATE

_SPIKE_KEYWORDS = ["lego", "technic", "spike", "mindstorms", "hub"]


def _probe_repl(port_path: str) -> bool:
    """Return True if the port responds to Ctrl-C with a MicroPython REPL prompt."""
    try:
        ser = serial.Serial(port_path, BAUD_RATE, timeout=0.5)
        ser.write(b"\x03")
        time.sleep(0.4)
        # use readline() not in_waiting — in_waiting unreliable on Linux CDC-ACM
        data = b""
        while True:
            chunk = ser.readline()
            if not chunk:
                break
            data += chunk
        ser.close()
        return b">" in data
    except Exception:
        return False


def detect_spike_port() -> str | None:
    """Return the serial port for a SPIKE Prime hub, or None if not found.

    Detection order:
      1. BOPIT_SERIAL_PORT environment variable
      2. Probe each ttyACM port for a live MicroPython REPL (highest-numbered first)
      3. Keyword match in port description
      4. ttyUSB fallback
      5. COM port fallback (Windows)
    """
    env_port = os.environ.get("BOPIT_SERIAL_PORT")
    if env_port:
        print(f"[Serial] Using BOPIT_SERIAL_PORT override: {env_port}")
        return env_port

    ports = list(serial.tools.list_ports.comports())

    # Sort highest-numbered first — SPIKE REPL is typically on the last ACM device
    acm_ports = sorted(
        [p.device for p in ports if "ttyACM" in p.device],
        reverse=True,
    )
    if acm_ports:
        print(f"[Serial] Probing ACM ports for REPL: {acm_ports}")
        for port_path in acm_ports:
            if _probe_repl(port_path):
                print(f"[Serial] REPL confirmed on: {port_path}")
                return port_path
        # Probe failed — use highest-numbered ACM (most likely to be REPL)
        print(f"[Serial] Probe got no response; using {acm_ports[0]}")
        return acm_ports[0]

    for port in ports:
        desc = " ".join(filter(None, [port.description, port.manufacturer])).lower()
        if any(kw in desc for kw in _SPIKE_KEYWORDS):
            print(f"[Serial] Detected SPIKE device: {port.device} ({port.description})")
            return port.device

    for port in ports:
        if "ttyUSB" in port.device:
            print(f"[Serial] Fallback ttyUSB: {port.device} ({port.description})")
            return port.device

    for port in ports:
        if port.device.startswith("COM"):
            print(f"[Serial] Fallback COM port: {port.device}")
            return port.device

    return None


def connect() -> serial.Serial:
    """Connect to the SPIKE Prime hub. Raises RuntimeError with diagnostics on failure."""
    port = detect_spike_port()
    if not port:
        available = [p.device for p in serial.tools.list_ports.comports()]
        raise RuntimeError(
            "No SPIKE Prime device found.\n"
            f"Available ports: {available or 'none'}\n"
            "Set BOPIT_SERIAL_PORT to specify a port manually.\n"
            "On Steam Deck, ensure you are in the 'uucp' group:\n"
            "  sudo usermod -aG uucp $USER  (then reboot)"
        )

    print(f"[Serial] Connecting to {port} at {BAUD_RATE} baud...")
    ser = serial.Serial(port, BAUD_RATE, timeout=1)
    print("[Serial] Connected.")
    return ser


def upload_hub_code(ser: serial.Serial, hub_code: str) -> None:
    """Interrupt the hub REPL, upload hub_code, and wait for HUB_READY."""
    debug = bool(os.environ.get("BOPIT_DEBUG"))

    def _read_response(wait: float) -> bytes:
        time.sleep(wait)
        data = b""
        while True:
            line = ser.readline()
            if not line:
                break
            data += line
        if debug and data:
            print(f"[Upload] << {repr(data)}")
        return data

    ser.reset_input_buffer()
    time.sleep(2)

    print("[Serial] Interrupting runtime...")
    ser.write(b"\x03\x03")
    _read_response(0.5)

    print("[Serial] Entering paste mode...")
    ser.write(b"\x05")
    resp = _read_response(0.5)
    if resp and debug:
        print(f"[Upload] Paste mode response: {repr(resp)}")

    print("[Serial] Uploading hub logic...")
    chunk_size = 128
    code_bytes = hub_code.encode("utf-8")
    for i in range(0, len(code_bytes), chunk_size):
        ser.write(code_bytes[i : i + chunk_size])
        time.sleep(0.05)

    time.sleep(0.5)
    ser.write(b"\x04")
    print("[Serial] Waiting for HUB_READY...")

    deadline = time.time() + 15
    buf = b""
    while time.time() < deadline:
        line = ser.readline()
        if not line:
            continue
        if debug:
            print(f"[Upload] << {repr(line)}")
        buf += line
        text = line.decode("utf-8", errors="replace").strip()
        if text == "HUB_READY":
            print("[Serial] HUB_READY — hub is running.")
            return
        if text.startswith("ERR:"):
            print(f"[Serial] Hub reported error: {text}")
            break

    print("[Serial] WARNING: HUB_READY not received. Hub may not be running.")
    if debug:
        print(f"[Upload] Buffer so far: {repr(buf)}")

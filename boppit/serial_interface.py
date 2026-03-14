import os
import time
import serial
import serial.tools.list_ports

from .config import BAUD_RATE

# Keywords that identify a LEGO SPIKE Prime hub in port descriptions
_SPIKE_KEYWORDS = ["lego", "technic", "spike", "mindstorms", "hub"]


def _probe_repl(port_path: str) -> bool:
    """Return True if the port responds to Ctrl-C with a MicroPython REPL prompt."""
    try:
        ser = serial.Serial(port_path, BAUD_RATE, timeout=0.5)
        ser.write(b"\x03")
        time.sleep(0.4)
        data = ser.read(max(ser.in_waiting, 1))
        ser.close()
        return b">" in data
    except Exception:
        return False


def detect_spike_port() -> str | None:
    """Return the serial port for a SPIKE Prime hub, or None if not found.

    Detection order:
      1. BOPIT_SERIAL_PORT environment variable (explicit override)
      2. Probe each ttyACM port for a live MicroPython REPL (handles hubs
         that expose multiple ACM devices — e.g. ttyACM0=storage, ttyACM1=REPL)
      3. Port whose description/manufacturer contains a SPIKE keyword
      4. First /dev/ttyUSB* device
      5. First COM* port (optional Windows compatibility)
    """
    env_port = os.environ.get("BOPIT_SERIAL_PORT")
    if env_port:
        print(f"[Serial] Using BOPIT_SERIAL_PORT override: {env_port}")
        return env_port

    ports = list(serial.tools.list_ports.comports())

    # Probe all ttyACM ports — SPIKE Prime REPL may not be on the first one
    acm_ports = sorted(
        [p.device for p in ports if "ttyACM" in p.device],
        reverse=True,   # try higher-numbered first (REPL is usually last)
    )
    if acm_ports:
        print(f"[Serial] Probing ACM ports for REPL: {acm_ports}")
        for port_path in acm_ports:
            if _probe_repl(port_path):
                print(f"[Serial] REPL confirmed on: {port_path}")
                return port_path
        # No port responded — fall back to first ACM anyway
        print(f"[Serial] No REPL probe response; falling back to {acm_ports[-1]}")
        return acm_ports[-1]

    # Keyword match (Windows / other Linux setups)
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
            "Set the BOPIT_SERIAL_PORT environment variable to specify a port manually.\n"
            "On Linux/Steam Deck, ensure your user is in the 'uucp' group:\n"
            "  sudo usermod -aG uucp $USER  (then reboot)"
        )

    print(f"[Serial] Connecting to {port} at {BAUD_RATE} baud...")
    ser = serial.Serial(port, BAUD_RATE, timeout=1)
    print("[Serial] Connected.")
    return ser


def upload_hub_code(ser: serial.Serial, hub_code: str) -> None:
    """Interrupt the hub REPL, upload hub_code, and execute it."""
    time.sleep(2)

    print("[Serial] Interrupting runtime...")
    ser.write(b"\x03\x03")
    time.sleep(0.5)

    print("[Serial] Entering paste mode...")
    ser.write(b"\x05")
    time.sleep(0.5)

    print("[Serial] Uploading hub logic...")
    chunk_size = 128
    code_bytes = hub_code.encode("utf-8")
    for i in range(0, len(code_bytes), chunk_size):
        ser.write(code_bytes[i : i + chunk_size])
        time.sleep(0.05)

    time.sleep(0.5)
    ser.write(b"\x04")
    print("[Serial] Hub logic uploaded.")
    time.sleep(1.0)

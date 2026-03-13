import os
import time
import serial
import serial.tools.list_ports

from .config import BAUD_RATE

# Keywords that identify a LEGO SPIKE Prime hub in port descriptions
_SPIKE_KEYWORDS = ["lego", "technic", "spike", "mindstorms", "hub"]


def detect_spike_port() -> str | None:
    """Return the serial port for a SPIKE Prime hub, or None if not found.

    Detection order:
      1. BOPIT_SERIAL_PORT environment variable (explicit override)
      2. Port whose description/manufacturer contains a SPIKE keyword
      3. First /dev/ttyACM* device (Linux CDC serial)
      4. First /dev/ttyUSB* device (Linux USB-serial adapter)
      5. First COM* port (optional Windows compatibility)
    """
    env_port = os.environ.get("BOPIT_SERIAL_PORT")
    if env_port:
        print(f"[Serial] Using BOPIT_SERIAL_PORT override: {env_port}")
        return env_port

    ports = list(serial.tools.list_ports.comports())

    for port in ports:
        desc = " ".join(filter(None, [port.description, port.manufacturer])).lower()
        if any(kw in desc for kw in _SPIKE_KEYWORDS):
            print(f"[Serial] Detected SPIKE device: {port.device} ({port.description})")
            return port.device

    for port in ports:
        if "ttyACM" in port.device:
            print(f"[Serial] Fallback ttyACM: {port.device} ({port.description})")
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
            "On Linux, ensure your user is in the 'dialout' group: sudo usermod -aG dialout $USER"
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

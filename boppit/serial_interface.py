import os
import time
import serial
import serial.tools.list_ports

from .config import BAUD_RATE

_SPIKE_KEYWORDS = ["lego", "technic", "spike", "mindstorms", "hub"]
_BATCH_SIZE = 5
_DELAY_LADDER = [0.040, 0.060, 0.100, 0.140, 0.200]  # seconds per line, escalates on error


def _probe_repl(port_path: str) -> bool:
    """Return True if the port responds to Ctrl-C with a MicroPython REPL prompt."""
    try:
        ser = serial.Serial(port_path, BAUD_RATE, timeout=0.5)
        ser.write(b"\x03")
        time.sleep(0.4)
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


def check_hub_ready(ser: serial.Serial) -> bool:
    """Return True if the hub is already running the game code.

    Sends CMD:STOP and waits up to 1 s for ACK:STOP.  If the hub responds it
    is already running — no upload needed.  Safe to call before upload_hub_code.
    """
    try:
        ser.reset_input_buffer()
        ser.write(b"CMD:STOP\n")
        deadline = time.time() + 1.0
        while time.time() < deadline:
            line = ser.readline()
            if line and b"ACK:STOP" in line:
                print("[Serial] Hub already running — skipping upload.")
                return True
        return False
    except Exception:
        return False


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
    """Upload hub_code to the SPIKE Prime via MicroPython paste mode.

    Sends lines in batches of _BATCH_SIZE with adaptive per-line delay.
    Starts at 40 ms/line and steps up the delay ladder each time a batch
    echo mismatch is detected.  On mismatch the paste session is cancelled,
    re-entered, already-verified batches are replayed fast, then the failed
    batch and beyond are re-sent at the new (slower) rate.
    """
    debug = bool(os.environ.get("BOPIT_DEBUG"))

    # Strip blank lines and pure-comment lines to minimise upload size
    lines = [
        line for line in hub_code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    batches = [lines[i : i + _BATCH_SIZE] for i in range(0, len(lines), _BATCH_SIZE)]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _enter_paste_mode() -> bool:
        ser.reset_input_buffer()
        time.sleep(1.0)
        ser.write(b"\x03\x03")
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.write(b"\x05")
        deadline = time.time() + 2.0
        resp = b""
        while time.time() < deadline:
            resp += ser.read(ser.in_waiting or 1)
            if b"paste mode" in resp:
                break
        if debug:
            print(f"[Upload] Paste mode response: {repr(resp)}")
        return b"paste mode" in resp

    def _send_lines(batch: list[str], delay: float) -> None:
        for line in batch:
            ser.write((line + "\n").encode("utf-8"))
            time.sleep(delay)

    def _send_and_verify(batch: list[str], delay: float) -> list[int]:
        """Send a batch, collect echo, return indices of mismatched lines."""
        _send_lines(batch, delay)

        # Paste mode echoes raw lines (no "=== " between them in batch).
        # Wait until we've seen at least len(batch) newlines in the echo.
        deadline = time.time() + max(3.0, len(batch) * delay * 3)
        echo = b""
        while time.time() < deadline:
            echo += ser.read(ser.in_waiting or 1)
            if echo.count(b"\n") >= len(batch):
                break

        if debug:
            print(f"[Upload] Echo ({len(echo)}B): {repr(echo)}")

        # Split on newlines, strip CR/whitespace, drop blank segments
        echoed = [
            seg.decode("utf-8", errors="replace").strip()
            for seg in echo.split(b"\n")
            if seg.strip()
        ]

        bad = []
        for i, sent in enumerate(batch):
            received = echoed[i] if i < len(echoed) else ""
            if sent.strip() != received:
                bad.append(i)
                if debug:
                    print(f"[Upload] Mismatch line {i}: "
                          f"sent={repr(sent.strip())} got={repr(received)}")
        return bad

    # ------------------------------------------------------------------
    # Upload loop — adaptive delay, per-batch error correction
    # ------------------------------------------------------------------
    delay_idx = 0           # current position in _DELAY_LADDER
    retry_from = 0          # first batch index that needs (re)verification
    buf = b""               # last HUB_READY wait buffer (for debug on failure)

    for attempt in range(1, len(_DELAY_LADDER) + 1):
        delay = _DELAY_LADDER[delay_idx]

        if not _enter_paste_mode():
            raise RuntimeError("Failed to enter MicroPython paste mode")

        print(f"[Serial] Uploading {len(lines)} lines "
              f"(attempt {attempt}, delay {int(delay*1000)} ms/line, "
              f"from batch {retry_from})...")

        # Fast-replay all already-verified batches at the current delay
        # (they passed before; use same delay for safety on the replay)
        for i in range(retry_from):
            _send_lines(batches[i], delay)
            # Drain their echo so the buffer stays clean
            time.sleep(len(batches[i]) * delay * 2)
            ser.reset_input_buffer()

        # Verify from retry_from onward
        failed_batch = None
        for i in range(retry_from, len(batches)):
            bad_indices = _send_and_verify(batches[i], delay)
            if bad_indices:
                print(f"[Serial] Batch {i} had {len(bad_indices)} bad line(s) "
                      f"— slowing down and retrying from batch {i}...")
                ser.write(b"\x03")   # Ctrl-C: cancel paste mode
                time.sleep(0.3)
                retry_from = i
                failed_batch = i
                delay_idx = min(delay_idx + 1, len(_DELAY_LADDER) - 1)
                break

        if failed_batch is not None:
            continue  # retry at the new delay

        # All batches passed — execute
        ser.write(b"\x04")
        print("[Serial] Waiting for HUB_READY...")

        deadline = time.time() + 10
        buf = b""
        ready = False
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
                ready = True
                break
            if "SyntaxError" in text or text.startswith("ERR:"):
                print(f"[Serial] Hub error (attempt {attempt}): {text}")
                retry_from = 0
                delay_idx = min(delay_idx + 1, len(_DELAY_LADDER) - 1)
                break

        if ready:
            return
        print(f"[Serial] Attempt {attempt} failed, retrying...")
        time.sleep(0.5)

    print(f"[Serial] WARNING: HUB_READY not received after {attempt} attempts.")
    if debug:
        print(f"[Upload] Last buffer: {repr(buf)}")

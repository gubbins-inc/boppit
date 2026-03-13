# MicroPython code uploaded to the LEGO SPIKE Prime hub at runtime.
# This string is sent verbatim over USB serial in paste mode (Ctrl-E / Ctrl-D).
# Do NOT change the protocol messages (ACK:, EVENT:, FX:, INPUT:, ERR:).

HUB_CODE = """
import hub
from hub import light
import sys
import select
import time
import math

# --- COLORS ---
CLR_OFF = 0
CLR_PINK = 1
CLR_PURPLE = 2
CLR_BLUE = 3
CLR_L_BLUE = 4
CLR_L_GREEN = 5
CLR_GREEN = 6
CLR_YELLOW = 7
CLR_ORANGE = 8
CLR_RED = 9
CLR_WHITE = 10

# --- CUSTOM PIXEL ARRAYS (0-100 Brightness) ---
# Twist (Clockwise Arrow)
PIXELS_TWIST = [
    0, 0, 100, 100, 0,
    0, 100, 0, 0, 100,
    0, 100, 0, 0, 100,
    100, 100, 100, 0, 100,
    0, 100, 0, 0, 100
]

# Untwist (Counter-Clockwise Arrow)
PIXELS_UNTWIST = [
    0, 100, 100, 0, 0,
    100, 0, 0, 100, 0,
    100, 0, 0, 100, 0,
    100, 0, 100, 100, 100,
    100, 0, 0, 100, 0
]

# Leave (Z shape for Sleep)
PIXELS_LEAVE = [
    100, 100, 100, 100, 100,
    0, 0, 0, 100, 0,
    0, 0, 100, 0, 0,
    0, 100, 0, 0, 0,
    100, 100, 100, 100, 100
]

# --- CONSTANTS ---
SHAKE_THRESHOLD = 1200
TWIST_THRESHOLD = 20
DEBOUNCE_MS = 500

print("HUB_READY")
hub.light_matrix.clear()

poll_obj = select.poll()
poll_obj.register(sys.stdin, select.POLLIN)

# State Variables
target_action = "NONE"
start_yaw = 0.0
last_event_time = 0
last_start_time = 0
feedback_end_time = 0

# Logic & FX Flags
shake_count = 0
last_shake_time = 0
fx_shake_sent = False
fx_twist_sent = False
fx_untwist_sent = False
fx_bop_sent = False
fx_bip_sent = False

def get_yaw():
    return hub.motion_sensor.tilt_angles()[0] / 10.0

def get_acc_mag():
    acc = hub.motion_sensor.acceleration()
    return math.sqrt(acc[0]**2 + acc[1]**2 + acc[2]**2)

try:
    while True:
        current_time = time.ticks_ms()

        # 1. CHECK FOR COMMANDS
        if poll_obj.poll(0):
            line = sys.stdin.readline().strip()

            if line.startswith("CMD:"):
                cmd = line.split(":")[1]
                target_action = cmd

                # Reset Game State for new round
                start_yaw = get_yaw()
                shake_count = 0
                fx_shake_sent = False
                fx_twist_sent = False
                fx_untwist_sent = False
                fx_bop_sent = False
                fx_bip_sent = False

                # Visual Feedback for Command
                if target_action == "BOP":
                    hub.light_matrix.show_image(hub.light_matrix.IMAGE_ARROW_W)
                    print("ACK:BOP")
                elif target_action == "BIP":
                    hub.light_matrix.show_image(hub.light_matrix.IMAGE_ARROW_E)
                    print("ACK:BIP")
                elif target_action == "TWIST":
                    hub.light_matrix.show(PIXELS_TWIST)
                    print("ACK:TWIST")
                elif target_action == "UNTWIST":
                    hub.light_matrix.show(PIXELS_UNTWIST)
                    print("ACK:UNTWIST")
                elif target_action == "SHAKE":
                    hub.light_matrix.show_image(hub.light_matrix.IMAGE_HAPPY)
                    print("ACK:SHAKE")
                elif target_action == "LEAVE":
                    hub.light_matrix.show(PIXELS_LEAVE)
                    print("ACK:LEAVE")
                elif target_action == "STOP":
                    hub.light_matrix.show_image(hub.light_matrix.IMAGE_SAD)
                    target_action = "NONE"
                    print("ACK:STOP")

        # 2. LIGHT CONTROL
        if current_time > feedback_end_time:
            if target_action == "BOP": light.color(light.POWER, CLR_BLUE)
            elif target_action == "BIP": light.color(light.POWER, CLR_PINK)
            elif target_action == "TWIST": light.color(light.POWER, CLR_YELLOW)
            elif target_action == "UNTWIST": light.color(light.POWER, CLR_ORANGE)
            elif target_action == "SHAKE": light.color(light.POWER, CLR_PURPLE)
            elif target_action == "LEAVE": light.color(light.POWER, CLR_L_BLUE)
            else:
                # IDLE PULSE (White)
                if (current_time // 500) % 2 == 0:
                    light.color(light.POWER, CLR_WHITE)
                else:
                    light.color(light.POWER, CLR_OFF)

        # 3. CHECK FOR START (LEFT or RIGHT Button)
        if target_action == "NONE":
            if hub.button.pressed(hub.button.LEFT) or hub.button.pressed(hub.button.RIGHT):
                if time.ticks_diff(current_time, last_start_time) > 2000:
                    print("INPUT:START")
                    last_start_time = current_time
                    light.color(light.POWER, CLR_ORANGE)
                    feedback_end_time = current_time + 500

        # 4. GAME LOGIC
        if target_action != "NONE" and time.ticks_diff(current_time, last_event_time) > DEBOUNCE_MS:

            # --- INPUT DETECTION ---
            is_bop = hub.button.pressed(hub.button.LEFT)
            is_bip = hub.button.pressed(hub.button.RIGHT)

            # Yaw Calculation (Signed)
            curr_yaw = get_yaw()
            diff = curr_yaw - start_yaw
            # Handle wrap-around (-180 to 180)
            if diff > 180: diff -= 360
            elif diff < -180: diff += 360

            is_twist = diff > TWIST_THRESHOLD
            is_untwist = diff < -TWIST_THRESHOLD

            # Shake Detection
            acc_mag = get_acc_mag()
            is_shake = False
            if acc_mag > SHAKE_THRESHOLD:
                if time.ticks_diff(current_time, last_shake_time) > 100:
                    shake_count += 1
                    last_shake_time = current_time
                    if shake_count == 1 and not fx_shake_sent:
                        print("FX:SHAKE")
                        fx_shake_sent = True
            if shake_count >= 3: is_shake = True

            # --- FX TRIGGERS ---
            if is_bop and not fx_bop_sent:
                print("FX:BOP")
                fx_bop_sent = True
            if is_bip and not fx_bip_sent:
                print("FX:BIP")
                fx_bip_sent = True
            if is_twist and not fx_twist_sent:
                print("FX:TWIST")
                fx_twist_sent = True
            if is_untwist and not fx_untwist_sent:
                print("FX:UNTWIST")
                fx_untwist_sent = True

            # --- RESULT EVALUATION ---
            result = ""
            any_action = is_bop or is_bip or is_twist or is_untwist or is_shake

            if target_action == "LEAVE":
                if any_action: result = "FAIL:MOVED"
                # Success for LEAVE is handled by PC timeout

            elif target_action == "BOP":
                if is_bop: result = "SUCCESS"
                elif any_action: result = "FAIL:WRONG_ACTION"

            elif target_action == "BIP":
                if is_bip: result = "SUCCESS"
                elif any_action: result = "FAIL:WRONG_ACTION"

            elif target_action == "TWIST":
                if is_twist: result = "SUCCESS"
                elif any_action: result = "FAIL:WRONG_ACTION"

            elif target_action == "UNTWIST":
                if is_untwist: result = "SUCCESS"
                elif any_action: result = "FAIL:WRONG_ACTION"

            elif target_action == "SHAKE":
                if is_shake: result = "SUCCESS"
                elif any_action: result = "FAIL:WRONG_ACTION"

            # --- SEND RESULT ---
            if result == "SUCCESS":
                hub.light_matrix.show_image(hub.light_matrix.IMAGE_YES)
                light.color(light.POWER, CLR_GREEN)
                feedback_end_time = current_time + 1000
                print("EVENT:SUCCESS")
                target_action = "NONE"
                last_event_time = current_time

            elif result.startswith("FAIL"):
                hub.light_matrix.show_image(hub.light_matrix.IMAGE_NO)
                light.color(light.POWER, CLR_RED)
                feedback_end_time = current_time + 1000
                print("EVENT:" + result)
                target_action = "NONE"
                last_event_time = current_time

        time.sleep(0.01)
except Exception as e:
    print("ERR:" + str(e))
"""

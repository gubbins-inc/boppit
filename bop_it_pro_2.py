import serial
import time
import sys
import threading
import random
import tkinter as tk
import tkinter.simpledialog as tkt
import os
import pygame
import cv2
from PIL import Image, ImageTk
import json 

# --- CONFIGURATION ---
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200
AUDIO_ROOT = r"D:\boppit_audio"
VIDEO_PATH = r"D:\boppit_audio\background.mp4"
HIGHSCORE_FILE = "highscore.json"

# --- HUB CODE (Firmware 3.6) ---
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
            
            is_twist = diff > TWIST_THRESHOLD      # Positive Rotation
            is_untwist = diff < -TWIST_THRESHOLD   # Negative Rotation
            
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

class AudioManager:
    def __init__(self, root_path):
        self.root = root_path
        pygame.mixer.init()
        pygame.mixer.set_reserved(3)
        self.sfx_channel = pygame.mixer.Channel(1)   
        self.voice_channel = pygame.mixer.Channel(2) 
        self.music_channel = pygame.mixer.Channel(3) 
        
        self.sfx_channel.set_volume(1.0)    
        self.voice_channel.set_volume(0.6)  
        
    def _play_random_from_folder(self, folder, channel):
        path = os.path.join(self.root, folder)
        if not os.path.exists(path): return
        files = [f for f in os.listdir(path) if f.endswith('.mp3')]
        if files:
            file = random.choice(files)
            channel.play(pygame.mixer.Sound(os.path.join(path, file)))

    def start_music(self):
        path = os.path.join(self.root, "themetune.mp3")
        if os.path.exists(path):
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.05) 
            pygame.mixer.music.play(-1)

    def stop_music(self):
        pygame.mixer.music.stop()

    def play_fx(self, action):
        filename_map = {
            "BOP": "bopped.mp3",
            "BIP": "bipped.mp3",
            "TWIST": "twisted.mp3",
            "UNTWIST": "untwisted.mp3",
            "SHAKE": "shook.mp3",
            "LEAVE": "left.mp3"
        }
        filename = filename_map.get(action)
        if filename:
            path = os.path.join(self.root, "fx", filename)
            if os.path.exists(path):
                self.sfx_channel.play(pygame.mixer.Sound(path))

    def play_ready(self): self._play_random_from_folder("ready", self.voice_channel)
    
    def play_command(self, action): 
        self._play_random_from_folder(action.lower(), self.voice_channel)
    
    def play_game_over_comment(self, score):
        self.stop_music()
        subfolder = "neutral"
        if score <= 10: subfolder = "insult"
        elif score <= 30: subfolder = "encourage"
        elif score <= 50: subfolder = "neutral"
        else: subfolder = "welldone"
            
        full_folder_path = os.path.join("endgame", subfolder)
        self._play_random_from_folder(full_folder_path, self.sfx_channel)

    def play_endgame_sequence(self, score, is_highscore, on_complete_callback):      
        time.sleep(0.1) 
        while self.sfx_channel.get_busy(): time.sleep(0.1)
        time.sleep(0.2) 

        path = ""
        if 0 <= score <= 50:
            path = os.path.join(self.root, "scoresnamed", f"{score}.mp3")
        else:
            folder = "scores_ranged"
            filename = "251-999.mp3"
            if 51 <= score <= 60: filename = "51-60.mp3"
            elif 61 <= score <= 70: filename = "61-70.mp3"
            elif 71 <= score <= 80: filename = "71-80.mp3"
            elif 81 <= score <= 90: filename = "81-90.mp3"
            elif 91 <= score <= 100: filename = "91-100.mp3"
            elif 101 <= score <= 150: filename = "101-150.mp3"
            elif 151 <= score <= 200: filename = "151-200.mp3"
            elif 201 <= score <= 250: filename = "201-250.mp3"
            path = os.path.join(self.root, folder, filename)

        if os.path.exists(path): 
            self.voice_channel.play(pygame.mixer.Sound(path))

        if is_highscore:
            time.sleep(0.1)
            while self.voice_channel.get_busy(): time.sleep(0.1)
            self._play_random_from_folder("highscore_trumpet", self.sfx_channel)
            time.sleep(0.1)
            while self.sfx_channel.get_busy(): time.sleep(0.1)
            self.sfx_channel.set_volume(0.2) 
            self._play_random_from_folder("highscore_celebrate", self.sfx_channel)
            self._play_random_from_folder("highscore_voice", self.voice_channel)
            time.sleep(0.1)
            while self.sfx_channel.get_busy(): time.sleep(0.1)
            self.sfx_channel.set_volume(1.0)
        
        if on_complete_callback: on_complete_callback()

class VideoPlayer:
    def __init__(self, video_path, label_widget):
        self.video_path = video_path
        self.label = label_widget
        self.cap = cv2.VideoCapture(video_path)
        self.playing = False
        self.running = True
        self.thread = threading.Thread(target=self._update_frame, daemon=True)
        self.thread.start()

    def play(self): self.playing = True
    def pause(self): self.playing = False

    def _update_frame(self):
        while self.running:
            if self.playing and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.resize(frame, (500, 400))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.label.imgtk = imgtk
                    self.label.configure(image=imgtk)
                    time.sleep(0.03)
                else:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                time.sleep(0.1)

class VisualTimer:
    def __init__(self, canvas, x, y, radius):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = radius
        self.running = False
        self.start_time = 0
        self.duration = 0
        self.arc_id = self.canvas.create_arc(x-radius, y-radius, x+radius, y+radius, 
                                             start=90, extent=0, fill="red", outline="white", width=2)

    def start(self, duration_sec):
        self.duration = duration_sec
        self.start_time = time.time()
        self.running = True
        self.update()

    def stop(self):
        self.running = False
        self.canvas.itemconfigure(self.arc_id, extent=0)

    def update(self):
        if not self.running: return
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            self.canvas.itemconfigure(self.arc_id, extent=359.9)
            self.running = False
            return
        angle = -(elapsed / self.duration) * 360
        self.canvas.itemconfigure(self.arc_id, extent=angle)
        self.canvas.after(50, self.update)

class BopItGame:
    def __init__(self, root, ser):
        self.root = root
        self.ser = ser
        self.running = True
        self.audio = AudioManager(AUDIO_ROOT)
        
        self.score= 0
        self.state = "IDLE"
        self.busy = False 
        self.current_action = None
        self.timer_id = None
        self.time_limit = 3.0
        self.action_history = [] 
        
        self.root.title("SPIKE Prime Bop-It Pro")
        self.root.geometry("500x450")
        
        self.lbl_video = tk.Label(root)
        self.lbl_video.place(x=0, y=0, width=500, height=450)
        
        self.cv_timer = tk.Canvas(root, width=60, height=60, bg="black", highlightthickness=0)
        self.cv_timer.place(x=430, y=10)
        self.visual_timer = VisualTimer(self.cv_timer, 30, 30, 25)
        
        self.lbl_time_text = tk.Label(root, text="3.00s", font=("Consolas", 10, "bold"), fg="white", bg="black")
        self.lbl_time_text.place(x=430, y=75, width=60)
        
        self.lbl_score = tk.Label(root, text="Score: 0", font=("Arial", 20, "bold"), fg="white", bg="black")
        self.lbl_score.pack(pady=20)
        
        self.lbl_instruction = tk.Label(root, text="Press Start", font=("Arial", 40, "bold"), fg="white", bg="black", wraplength=480)
        self.lbl_instruction.pack(expand=True)
        
        self.btn_start = tk.Button(root, text="START GAME", font=("Arial", 14), command=self.start_game)
        self.btn_start.pack(pady=20)
        
        self.lbl_status = tk.Label(root, text="Hub Status: Connected", font=("Consolas", 10), fg="white", bg="black")
        self.lbl_status.pack(side="bottom", anchor="e")
        
        self.lbl_highscore = tk.Label(root, text="High Score: -", font=("Arial", 12), fg="yellow", bg="black")
        self.lbl_highscore.place(x=10, y=420)

        self.video = VideoPlayer(VIDEO_PATH, self.lbl_video)
        self.thread = threading.Thread(target=self.serial_listener, daemon=True)
        self.thread.start()
        
        self.update_highscore_display()

    def serial_listener(self):
        while self.running:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='replace').strip()
                    
                    if line.startswith("FX:"):
                        action = line.split(":")[1]
                        self.root.after(0, lambda a=action: self.audio.play_fx(a))
                    
                    elif line == "INPUT:START":
                        if self.state != "PLAYING" and not self.busy:
                            self.root.after(0, self.start_game)

                    elif line == "EVENT:SUCCESS": 
                        self.root.after(0, self.handle_success)
                    elif line.startswith("EVENT:FAIL"):
                        reason = line.split(":")[2] if len(line.split(":")) > 2 else "FAIL"
                        self.root.after(0, lambda r=reason: self.handle_fail(r))
                    elif line.startswith("ACK:"): 
                        print(f"[HUB] {line}")
                    elif line.startswith("ERR:"):
                        print(f"[HUB ERROR] {line}")
                        
            except Exception as e:
                print(f"Serial Error: {e}")
                break

    def send_cmd(self, cmd):
        try:
            full_cmd = f"CMD:{cmd}\n"
            self.ser.write(full_cmd.encode('utf-8'))
        except Exception as e:
            print(f"Write Error: {e}")

    def get_highscore_data(self):
        try:
            if os.path.exists(HIGHSCORE_FILE):
                with open(HIGHSCORE_FILE, "r") as f:
                    data = json.load(f)
                    return data.get("score", 0), data.get("player", "None")
        except:
            pass
        return 0, "None"

    def update_highscore_display(self):
        score, player = self.get_highscore_data()
        self.lbl_highscore.config(text=f"High Score: {score} ({player})")

    def check_and_save_highscore(self):
        current_high, _ = self.get_highscore_data()
        if self.score > current_high:
            name = tkt.askstring("New High Score!", f"New Record: {self.score}!\nEnter your name:")
            if not name: name = "Anonymous"
            data = {"score": self.score, "player": name}
            with open(HIGHSCORE_FILE, "w") as f:
                json.dump(data, f)
            self.update_highscore_display()
        self.busy = False
        self.btn_start.config(state="normal")

    def get_next_action(self):
        actions = ["BOP", "TWIST", "SHAKE"]
        if self.score >= 51: actions.append("BIP")
        if self.score >= 66: actions.append("UNTWIST")
        if self.score >= 81: actions.append("LEAVE")
        
        if not self.action_history: return random.choice(actions)
        last_action = self.action_history[-1]
        
        if len(self.action_history) >= 2 and self.action_history[-1] == self.action_history[-2]:
            if last_action in actions: actions.remove(last_action)
            return random.choice(actions)
            
        return random.choice(actions)

    def start_game(self):
        if self.busy: return
        self.score= 0
        self.action_history = [] 
        self.lbl_score.config(text=f"Score: {self.score}")
        self.btn_start.pack_forget()
        self.audio.play_ready()
        self.root.after(1500, self.begin_music_and_round)

    def begin_music_and_round(self):
        self.audio.start_music()
        self.video.play()
        self.next_round()

    def next_round(self):
        self.state = "PLAYING"
        self.current_action = self.get_next_action()
        self.action_history.append(self.current_action)
        
        display_text = f"{self.current_action} IT!"
        self.lbl_instruction.config(text=display_text, fg="white", bg="black")
        
        self.audio.play_command(self.current_action)
        self.send_cmd(self.current_action)
        
        self.time_limit = max(1.0, 3.0 - (self.score * 0.04))
        self.lbl_time_text.config(text=f"{self.time_limit:.2f}s")
        
        self.visual_timer.start(self.time_limit)
        
        if self.timer_id: self.root.after_cancel(self.timer_id)
        self.timer_id = self.root.after(int(self.time_limit * 1000), self.handle_timeout)

    def handle_success(self):
        if self.state != "PLAYING": return
        print(f"[PC] RESULT: PASS | Target: {self.current_action}")
        self.visual_timer.stop()
        if self.timer_id: self.root.after_cancel(self.timer_id)
        self.score += 1
        self.lbl_score.config(text=f"Score: {self.score}")
        self.lbl_instruction.config(text="GOOD!", fg="#00ff00")
        self.root.after(1000, self.next_round)

    def handle_fail(self, reason):
        if self.state != "PLAYING": return
        print(f"[PC] RESULT: FAIL | Reason: {reason} | Target: {self.current_action}")
        self.game_over(f"WRONG MOVE!")

    def handle_timeout(self):
        if self.state != "PLAYING": return
        
        if self.current_action == "LEAVE":
            self.audio.play_fx("LEAVE") 
            self.handle_success()
        else:
            print(f"[PC] RESULT: FAIL | Reason: TIMEOUT | Target: {self.current_action}")
            self.send_cmd("STOP")
            self.game_over("TOO SLOW!")

    def on_audio_sequence_complete(self):
        self.root.after(0, self.check_and_save_highscore)

    def game_over(self, reason):
        self.state = "GAME_OVER"
        self.busy = True
        self.btn_start.config(state="disabled")
        
        self.visual_timer.stop()
        if self.timer_id: self.root.after_cancel(self.timer_id)
        self.video.pause()
        self.lbl_instruction.config(text=reason, fg="red", bg="black")
        
        current_high, _ = self.get_highscore_data()
        is_new_record = self.score > current_high
        
        self.audio.play_game_over_comment(self.score)
        threading.Thread(target=self.audio.play_endgame_sequence, 
                         args=(self.score, is_new_record, self.on_audio_sequence_complete), 
                         daemon=True).start()
        
        self.btn_start.pack(pady=20)
        self.btn_start.config(text="TRY AGAIN")

if __name__ == "__main__":
    ser = None
    try:
        print(f"Connecting to {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)

        print("Interrupting Runtime...")
        ser.write(b'\x03\x03') 
        time.sleep(0.5)
        print("Uploading Hub Logic...")
        ser.write(b'\x05') 
        time.sleep(0.5)
        
        chunk_size = 128
        code_bytes = HUB_CODE.encode('utf-8')
        for i in range(0, len(code_bytes), chunk_size):
            ser.write(code_bytes[i:i+chunk_size])
            time.sleep(0.05)
        
        time.sleep(0.5)
        ser.write(b'\x04') 
        print("Hub Logic Uploaded.")
        time.sleep(1.0)

        root = tk.Tk()
        game = BopItGame(root, ser)
        root.mainloop()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
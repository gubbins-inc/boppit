import time
import json
import random
import threading
import tkinter as tk

import cv2
import pygame
from PIL import Image, ImageTk

from .audio import AudioManager
from .config import VIDEO_PATH, HIGHSCORE_FILE, ACTIONS_IMAGE_PATH

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class VideoPlayer:
    def __init__(self, video_path, label_widget):
        self.video_path = str(video_path)
        self.label = label_widget
        self.cap = cv2.VideoCapture(self.video_path)
        self.playing = False
        self.running = True
        self.thread = threading.Thread(target=self._update_frame, daemon=True)
        self.thread.start()

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

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
        self.arc_id = self.canvas.create_arc(
            x - radius, y - radius, x + radius, y + radius,
            start=90, extent=0, fill="red", outline="white", width=2
        )

    def start(self, duration_sec):
        self.duration = duration_sec
        self.start_time = time.time()
        self.running = True
        self.update()

    def stop(self):
        self.running = False
        self.canvas.itemconfigure(self.arc_id, extent=0)

    def update(self):
        if not self.running:
            return
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
        self.audio = AudioManager()

        self.score = 0
        self.state = "IDLE"
        self.busy = False
        self.current_action = None
        self.timer_id = None
        self.time_limit = 3.0
        self.action_history = []

        # Initials entry state
        self._initials = ["A", "A", "A"]
        self._initial_idx = 0          # which slot (0-2) is being edited
        self._initial_letter_idx = 0   # index into _ALPHABET for current slot

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

        self.lbl_initials_hint = tk.Label(root, text="", font=("Consolas", 11), fg="#aaaaaa", bg="black")
        self.lbl_initials_hint.pack()

        self.btn_start = tk.Button(root, text="START GAME", font=("Arial", 14), command=self.start_game)
        self.btn_start.pack(pady=20)

        self.lbl_status = tk.Label(root, text="Hub Status: Connected", font=("Consolas", 10), fg="white", bg="black")
        self.lbl_status.pack(side="bottom", anchor="e")

        self.lbl_highscore = tk.Label(root, text="High Score: -", font=("Arial", 12), fg="yellow", bg="black")
        self.lbl_highscore.place(x=10, y=420)

        self._actions_photo = None
        self._load_actions_image()

        self.video = VideoPlayer(VIDEO_PATH, self.lbl_video)
        self.thread = threading.Thread(target=self.serial_listener, daemon=True)
        self.thread.start()

        self._show_actions_image()
        self.update_highscore_display()

    # ------------------------------------------------------------------
    # Actions image
    # ------------------------------------------------------------------

    def _load_actions_image(self):
        if ACTIONS_IMAGE_PATH.exists():
            img = Image.open(str(ACTIONS_IMAGE_PATH))
            img = img.resize((500, 400), Image.LANCZOS)
            self._actions_photo = ImageTk.PhotoImage(img)

    def _show_actions_image(self):
        if self._actions_photo:
            self.lbl_video.imgtk = self._actions_photo
            self.lbl_video.configure(image=self._actions_photo)

    def _hide_actions_image(self):
        self.lbl_video.configure(image="")

    # ------------------------------------------------------------------
    # Serial listener
    # ------------------------------------------------------------------

    def serial_listener(self):
        import os
        debug = bool(os.environ.get("BOPIT_DEBUG"))
        while self.running:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if debug:
                    print(f"[SERIAL] {repr(line)}")

                if self.state == "ENTERING_INITIALS":
                    self._handle_initials_serial(line)
                    continue

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

    # ------------------------------------------------------------------
    # Hub command
    # ------------------------------------------------------------------

    def send_cmd(self, cmd):
        try:
            self.ser.write(f"CMD:{cmd}\n".encode("utf-8"))
        except Exception as e:
            print(f"Write Error: {e}")

    # ------------------------------------------------------------------
    # High score
    # ------------------------------------------------------------------

    def get_highscore_data(self):
        try:
            if HIGHSCORE_FILE.exists():
                with HIGHSCORE_FILE.open("r") as f:
                    data = json.load(f)
                    return data.get("score", 0), data.get("player", "None")
        except Exception:
            pass
        return 0, "None"

    def update_highscore_display(self):
        score, player = self.get_highscore_data()
        self.lbl_highscore.config(text=f"High Score: {score} ({player})")

    def check_and_save_highscore(self):
        current_high, _ = self.get_highscore_data()
        if self.score > current_high:
            self.root.after(0, self.start_initials_entry)
        else:
            self.busy = False
            self.root.after(0, lambda: self.btn_start.config(state="normal"))

    # ------------------------------------------------------------------
    # Initials entry via hub
    # ------------------------------------------------------------------

    def start_initials_entry(self):
        self.state = "ENTERING_INITIALS"
        self._initials = ["A", "A", "A"]
        self._initial_idx = 0
        self._initial_letter_idx = 0

        self.lbl_score.config(text=f"NEW RECORD: {self.score}!")
        self.lbl_initials_hint.config(
            text="BIP \u2191  BOP \u2193  SHAKE: select  TWIST: done"
        )
        self._update_initials_display()
        self.send_cmd("SHAKE")  # hub listens for shake; BIP/BOP arrive as FX events

    def _update_initials_display(self):
        parts = []
        for i, letter in enumerate(self._initials):
            if i < self._initial_idx:
                parts.append(letter)          # confirmed
            elif i == self._initial_idx:
                parts.append(f"[{letter}]")  # being selected
            else:
                parts.append("_")             # not yet reached
        self.lbl_instruction.config(text="  ".join(parts), fg="yellow", bg="black")

    def _handle_initials_serial(self, line):
        if line.startswith("FX:"):
            fx = line.split(":")[1]
            if fx == "BIP":
                self.root.after(0, self._initial_letter_up)
            elif fx == "BOP":
                self.root.after(0, self._initial_letter_down)
            elif fx == "UNTWIST":
                self.root.after(0, self._initial_submit)

        elif line == "EVENT:SUCCESS":
            # Shake confirmed — if we were in submit-wait mode it's a twist success
            if self._initial_idx >= 3:
                self.root.after(0, self._initial_submit)
            else:
                self.root.after(0, self._initial_confirm_letter)

        elif line.startswith("EVENT:FAIL"):
            # Re-arm hub for next input
            if self._initial_idx >= 3:
                self.send_cmd("TWIST")
            else:
                self.send_cmd("SHAKE")

        elif line.startswith("ACK:"):
            print(f"[HUB] {line}")

    def _initial_letter_up(self):
        self._initial_letter_idx = (self._initial_letter_idx + 1) % 26
        self._initials[self._initial_idx] = _ALPHABET[self._initial_letter_idx]
        self._update_initials_display()
        self.send_cmd("SHAKE")

    def _initial_letter_down(self):
        self._initial_letter_idx = (self._initial_letter_idx - 1) % 26
        self._initials[self._initial_idx] = _ALPHABET[self._initial_letter_idx]
        self._update_initials_display()
        self.send_cmd("SHAKE")

    def _initial_confirm_letter(self):
        self._initial_idx += 1
        self._initial_letter_idx = 0
        if self._initial_idx >= 3:
            # All 3 letters chosen — wait for twist to submit
            self.lbl_initials_hint.config(text="TWIST or UNTWIST to submit")
            self._update_initials_display()
            self.send_cmd("TWIST")
        else:
            self._initials[self._initial_idx] = _ALPHABET[0]
            self._update_initials_display()
            self.send_cmd("SHAKE")

    def _initial_submit(self):
        initials = "".join(self._initials)
        print(f"[PC] Initials entered: {initials}")

        data = {"score": self.score, "player": initials}
        with HIGHSCORE_FILE.open("w") as f:
            json.dump(data, f)

        self.update_highscore_display()
        self.lbl_initials_hint.config(text="")
        self.lbl_score.config(text=f"Score: {self.score}")
        self.state = "GAME_OVER"
        self.busy = False
        self.btn_start.config(state="normal")

    # ------------------------------------------------------------------
    # Game logic (unchanged)
    # ------------------------------------------------------------------

    def get_next_action(self):
        actions = ["BOP", "TWIST", "SHAKE"]
        if self.score >= 51:
            actions.append("BIP")
        if self.score >= 66:
            actions.append("UNTWIST")
        if self.score >= 81:
            actions.append("LEAVE")

        if not self.action_history:
            return random.choice(actions)
        last_action = self.action_history[-1]

        if len(self.action_history) >= 2 and self.action_history[-1] == self.action_history[-2]:
            if last_action in actions:
                actions.remove(last_action)
            return random.choice(actions)

        return random.choice(actions)

    def start_game(self):
        if self.busy:
            return
        self.score = 0
        self.action_history = []
        self.lbl_score.config(text=f"Score: {self.score}")
        self.lbl_initials_hint.config(text="")
        self.btn_start.pack_forget()
        self.audio.play_ready()
        self.root.after(1500, self.begin_music_and_round)

    def begin_music_and_round(self):
        self._hide_actions_image()
        self.audio.start_music()
        self.video.play()
        self.next_round()

    def next_round(self):
        self.state = "PLAYING"
        self.current_action = self.get_next_action()
        self.action_history.append(self.current_action)

        self.lbl_instruction.config(text=f"{self.current_action} IT!", fg="white", bg="black")

        self.audio.play_command(self.current_action)
        self.send_cmd(self.current_action)

        self.time_limit = max(1.0, 3.0 - (self.score * 0.04))
        self.lbl_time_text.config(text=f"{self.time_limit:.2f}s")

        self.visual_timer.start(self.time_limit)

        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.timer_id = self.root.after(int(self.time_limit * 1000), self.handle_timeout)

    def handle_success(self):
        if self.state != "PLAYING":
            return
        print(f"[PC] RESULT: PASS | Target: {self.current_action}")
        self.visual_timer.stop()
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.score += 1
        self.lbl_score.config(text=f"Score: {self.score}")
        self.lbl_instruction.config(text="GOOD!", fg="#00ff00")
        self.root.after(1000, self.next_round)

    def handle_fail(self, reason):
        if self.state != "PLAYING":
            return
        print(f"[PC] RESULT: FAIL | Reason: {reason} | Target: {self.current_action}")
        self.game_over("WRONG MOVE!")

    def handle_timeout(self):
        if self.state != "PLAYING":
            return

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
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.video.pause()
        self.lbl_instruction.config(text=reason, fg="red", bg="black")
        self._show_actions_image()

        current_high, _ = self.get_highscore_data()
        is_new_record = self.score > current_high

        self.audio.play_game_over_comment(self.score)
        threading.Thread(
            target=self.audio.play_endgame_sequence,
            args=(self.score, is_new_record, self.on_audio_sequence_complete),
            daemon=True,
        ).start()

        self.btn_start.pack(pady=20)
        self.btn_start.config(text="TRY AGAIN")

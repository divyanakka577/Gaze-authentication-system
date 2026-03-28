import customtkinter as ctk
import cv2
from PIL import Image
import mysql.connector
import face_recognition
import base64
import numpy as np
import threading
import sys
import webview

from gaze_tracking_module import authenticate_gaze, compare_coordinates

# ================= CONFIG =================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

WINDOW_W, WINDOW_H = 1920, 1080
DB = {
    "host": "localhost",
    "user": "root",
    "password": "Divya@123",
    "database": "user_auth"
}


class Camera:
    def __init__(self):
        self.cap = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if not self.running:
                backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
                for backend in backends:
                    cap = cv2.VideoCapture(0, backend)
                    if not cap or not cap.isOpened():
                        if cap:
                            cap.release()
                        continue
                    try:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    except cv2.error:
                        # Some Windows camera drivers reject property changes.
                        pass
                    self.cap = cap
                    self.running = True
                    return True
                return False
            return True

    def stop(self):
        with self.lock:
            self.running = False
            if self.cap:
                self.cap.release()
                self.cap = None

    def read(self):
        with self.lock:
            if not self.running or self.cap is None:
                return None
            ret, frame = self.cap.read()
            return frame if ret else None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Secure Gaze Auth")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.camera = Camera()
        self.authenticated_face_encoding = None
        self.gaze_status = {"authorized": True, "reason": ""}
        self.gaze_thread = None
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkFrame(self)
        self.left.grid(row=0, column=0, sticky="nsew")
        self.right = ctk.CTkFrame(self)
        self.right.grid(row=0, column=1, sticky="nsew")
        self.cam_label = ctk.CTkLabel(self.right, text="")
        self.cam_label.pack(expand=True, fill="both")

        self.show_register()

    def reset_session(self):
        self.authenticated_face_encoding = None
        self.gaze_status = {"authorized": True, "reason": ""}

    def decode_face_encoding(self, face_data):
        try:
            stored = np.frombuffer(base64.b64decode(face_data), dtype=np.float64)
        except Exception:
            return None
        return stored if stored.shape == (128,) else None

    def capture_face_encoding(self, attempts=10):
        last_error = "Face not detected"
        for _ in range(attempts):
            frame = self.camera.read()
            if frame is None:
                last_error = "Camera frame unavailable"
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            if len(face_locations) == 0:
                last_error = "No face detected"
                continue
            if len(face_locations) > 1:
                last_error = "Multiple faces detected"
                continue

            encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            if encodings:
                return encodings[0], None
            last_error = "Face could not be encoded"

        return None, last_error

    def set_login_button_state(self, state):
        if hasattr(self, "login_btn") and self.login_btn.winfo_exists():
            self.login_btn.configure(state=state)

    def start_camera_feed(self, ready_callback=None):
        def worker():
            started = self.camera.start()
            if started:
                self.after(10, self.update_cam_ui)
                if ready_callback:
                    self.after(100, ready_callback)
            elif ready_callback:
                self.after(100, lambda: ready_callback(False))

        threading.Thread(target=worker, daemon=True).start()

    def wait_for_camera_ready(self, on_ready, on_failed=None, attempts=20, delay=150):
        def poll(remaining):
            frame = self.camera.read()
            if frame is not None:
                on_ready()
                return
            if remaining <= 0:
                if on_failed:
                    on_failed()
                return
            self.after(delay, lambda: poll(remaining - 1))

        poll(attempts)

    def update_cam_ui(self):
        if not self.camera.running:
            return
        frame = self.camera.read()
        if frame is not None:
            img = Image.fromarray(cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB))
            ctk_img = ctk.CTkImage(light_image=img, size=(600, 400))
            try:
                self.cam_label.configure(image=ctk_img)
                self.cam_label.image = ctk_img
            except Exception:
                pass
        self.after(15, self.update_cam_ui)

    def show_register(self):
        self.reset_session()
        self.right.grid(row=0, column=1, sticky="nsew")
        self.left.grid_configure(columnspan=1)
        self.camera.stop()
        [w.destroy() for w in self.left.winfo_children()]

        card = ctk.CTkFrame(self.left, corner_radius=20, width=400, height=600)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="Register", font=("Arial", 28, "bold")).pack(pady=30)
        self.u = ctk.CTkEntry(card, placeholder_text="Username", width=300)
        self.p = ctk.CTkEntry(card, placeholder_text="Password", show="*", width=300)
        self.u.pack(pady=10)
        self.p.pack(pady=10)

        self.status = ctk.CTkLabel(card, text="Status: Ready", text_color="gray")
        self.status.pack(pady=10)

        ctk.CTkButton(card, text="Complete Registration", command=self.handle_reg).pack(pady=10)
        ctk.CTkButton(
            card,
            text="Already have an account? Login",
            fg_color="transparent",
            border_width=1,
            command=self.show_login,
        ).pack(pady=20)

        self.start_camera_feed()

    def handle_reg(self):
        username = self.u.get().strip()
        password = self.p.get()
        if not username or not password:
            self.status.configure(text="Enter username and password", text_color="red")
            return

        frame = self.camera.read()
        if frame is None:
            self.status.configure(text="Camera frame unavailable", text_color="red")
            return

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        if len(face_locations) == 0:
            self.status.configure(text="No face detected", text_color="red")
            return
        if len(face_locations) > 1:
            self.status.configure(text="Only one face is allowed during registration", text_color="red")
            return

        enc = face_recognition.face_encodings(rgb_frame, face_locations)
        if enc:
            face_str = base64.b64encode(enc[0].tobytes()).decode()
            conn = mysql.connector.connect(**DB)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE username=%s LIMIT 1", (username,))
            if cur.fetchone():
                conn.close()
                self.status.configure(text="Username already exists", text_color="red")
                return
            cur.execute(
                "INSERT INTO users (username, password, face_data) VALUES (%s,%s,%s)",
                (username, password, face_str),
            )
            conn.commit()
            conn.close()
            self.status.configure(text="Registered!", text_color="green")
        else:
            self.status.configure(text="Face could not be encoded", text_color="red")

    def show_login(self):
        self.reset_session()
        self.camera.stop()
        [w.destroy() for w in self.left.winfo_children()]
        card = ctk.CTkFrame(self.left, corner_radius=20, width=400, height=620)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        ctk.CTkLabel(card, text="Login", font=("Arial", 28, "bold")).pack(pady=30)
        self.lu = ctk.CTkEntry(card, placeholder_text="Username", width=300)
        self.lp = ctk.CTkEntry(card, placeholder_text="Password", show="*", width=300)
        self.lu.pack(pady=10)
        self.lp.pack(pady=10)
        self.lstatus = ctk.CTkLabel(card, text="Status: Starting camera...")
        self.lstatus.pack(pady=10)
        self.login_btn = ctk.CTkButton(card, text="Verify Identity", command=self.handle_login, state="disabled")
        self.login_btn.pack(pady=20)
        ctk.CTkButton(
            card,
            text="Back to Registration",
            fg_color="transparent",
            border_width=1,
            command=self.show_register,
        ).pack(pady=10)
        self.start_camera_feed(ready_callback=self.prepare_login_retry)

    def prepare_login_retry(self, started=True):
        if not started:
            self.lstatus.configure(text="Unable to start camera", text_color="red")
            return

        def mark_ready():
            self.lstatus.configure(text="Status: Waiting", text_color="white")
            self.set_login_button_state("normal")

        def mark_failed():
            self.lstatus.configure(text="Camera not ready. Please wait and try again.", text_color="red")
            self.set_login_button_state("normal")

        self.wait_for_camera_ready(mark_ready, mark_failed)

    def handle_login(self):
        username = self.lu.get().strip()
        password = self.lp.get()
        if not username or not password:
            self.lstatus.configure(text="Enter username and password", text_color="red")
            return

        self.set_login_button_state("disabled")
        self.lstatus.configure(text="Checking credentials and capturing face...", text_color="yellow")
        self.update_idletasks()

        conn = mysql.connector.connect(**DB)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password),
        )
        user = cur.fetchone()
        conn.close()
        if not user:
            self.lstatus.configure(text="Invalid Credentials", text_color="red")
            self.set_login_button_state("normal")
            return

        stored = self.decode_face_encoding(user["face_data"])
        if stored is None:
            self.lstatus.configure(text="Stored face data is invalid", text_color="red")
            self.set_login_button_state("normal")
            return

        live_encoding, capture_error = self.capture_face_encoding()
        if live_encoding is None:
            self.lstatus.configure(text=capture_error, text_color="red")
            self.set_login_button_state("normal")
            return

        distance = face_recognition.face_distance([stored], live_encoding)[0]
        if distance <= 0.50:
            self.authenticated_face_encoding = stored
            self.lstatus.configure(text="Face verified. Start gaze authentication.", text_color="green")
            self.after(500, self.show_gaze)
        else:
            self.lstatus.configure(text=f"Face mismatch (distance: {distance:.2f})", text_color="red")
            self.set_login_button_state("normal")

    def show_gaze(self):
        if self.authenticated_face_encoding is None:
            self.show_login()
            return

        self.camera.stop()
        [w.destroy() for w in self.left.winfo_children()]
        self.terminate = False
        self.m_coords, self.g_coords = [], []
        self.gaze_status = {"authorized": True, "reason": ""}

        container = ctk.CTkFrame(self.left)
        container.pack(expand=True, fill="both", padx=10, pady=10)
        self.g_cam = ctk.CTkLabel(container, text="")
        self.g_cam.pack(side="left", expand=True)
        self.g_maze = ctk.CTkLabel(container, text="")
        self.g_maze.pack(side="right", expand=True)
        self.g_status = ctk.CTkLabel(
            self.left,
            text="Keep the same person in front of the camera during gaze verification.",
        )
        self.g_status.pack(pady=(10, 0))
        ctk.CTkButton(self.left, text="Finish Authentication", command=self.finish_gaze).pack(pady=10)
        self.gaze_thread = threading.Thread(
            target=authenticate_gaze,
            args=(
                lambda: self.terminate,
                self.m_coords,
                self.g_coords,
                self.update_g_ui,
                self.authenticated_face_encoding.copy(),
                self.gaze_status,
            ),
            daemon=True,
        )
        self.gaze_thread.start()
        self.after(200, self.monitor_gaze_session)

    def wait_for_gaze_shutdown(self, callback, attempts=25, delay=120):
        if self.gaze_thread is None:
            self.gaze_thread = None
            callback()
            return

        if not self.gaze_thread.is_alive():
            self.gaze_thread = None
            callback()
            return

        if attempts <= 0:
            self.gaze_thread = None
            callback()
            return

        self.after(delay, lambda: self.wait_for_gaze_shutdown(callback, attempts - 1, delay))

    def restart_login_after_gaze(self, message):
        self.terminate = True
        self.wait_for_gaze_shutdown(lambda: self.show_login_error(message))

    def monitor_gaze_session(self):
        if self.terminate:
            return
        if not self.gaze_status.get("authorized", True):
            self.restart_login_after_gaze(self.gaze_status.get("reason", "Gaze authentication failed."))
            return
        self.after(200, self.monitor_gaze_session)

    def update_g_ui(self, cam, maze, status_text=None):
        try:
            if not self.g_cam.winfo_exists() or not self.g_maze.winfo_exists():
                return

            c_img = ctk.CTkImage(Image.fromarray(cv2.cvtColor(cam, cv2.COLOR_BGR2RGB)), size=(500, 350))
            m_img = ctk.CTkImage(Image.fromarray(cv2.cvtColor(maze, cv2.COLOR_BGR2RGB)), size=(500, 350))

            self.g_cam.configure(image=c_img)
            self.g_cam.image = c_img
            self.g_maze.configure(image=m_img)
            self.g_maze.image = m_img
            if status_text and hasattr(self, "g_status") and self.g_status.winfo_exists():
                self.g_status.configure(text=status_text)
        except Exception:
            pass

    def finish_gaze(self):
        self.terminate = True
        if not self.gaze_status.get("authorized", True):
            self.restart_login_after_gaze(self.gaze_status.get("reason", "Identity changed during gaze verification."))
            return
        if compare_coordinates(self.m_coords, self.g_coords):
            self.show_success()
        else:
            self.restart_login_after_gaze("Gaze pattern did not match. Please try again.")

    def show_login_error(self, message):
        self.show_login()
        if hasattr(self, "lstatus"):
            self.lstatus.configure(text=message, text_color="red")

    def show_success(self):
        [w.destroy() for w in self.left.winfo_children()]
        self.right.grid_forget()
        self.left.grid_configure(columnspan=2)
        self.success_lbl = ctk.CTkLabel(self.left, text="", font=("Arial", 30, "bold"), text_color="green")
        self.success_lbl.pack(pady=150)
        self.countdown(5)

    def countdown(self, count):
        if count > 0:
            self.success_lbl.configure(text=f"ACCESS GRANTED\nLoading Secure Portal in {count}...")
            self.after(1000, lambda: self.countdown(count - 1))
        else:
            self.open_portal()

    def open_portal(self):
        webview.create_window('Authorized Portal', 'file:///C:/Users/M%20Divya/Stage1/Demo/test.html', width=1920, height=1080)
        webview.start()
        self.show_register()

    def on_closing(self):
        self.camera.stop()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    App().mainloop()

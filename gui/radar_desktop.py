"""
=====================================================================================
 AXIS Site Designer / VMS - Standalone Python Desktop HUD
 Scandinavian Clean Security Architecture (Light Mode Theme)
=====================================================================================
 Requirements:
   pip install pyserial
 Usage:
   python radar_desktop.py [COM_PORT]
=====================================================================================
"""

import sys
import math
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class AxisRadarDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AXIS Site Designer - RF Multipath Sensing Station (ESP32 + ESP8266)")
        self.geometry("1040x720")
        self.configure(bg="#edf1f5")

        # Telemetry State
        self.motion_score = 0.0
        self.threshold = 25.0
        self.baseline = 8.5
        self.is_alert = False
        self.sweep_angle = 0.0
        self.blips = []  # list of [angle, radius, intensity]

        # Waveform History
        self.history_len = 100
        self.motion_history = [0.0] * self.history_len
        self.threshold_history = [25.0] * self.history_len

        # Serial Thread State
        self.ser = None
        self.is_running = False
        self.demo_mode = False

        self._build_ui()
        self._animate()

    def _build_ui(self):
        # 1. Top Axis Header Bar
        header = tk.Frame(self, bg="#ffffff", bd=0, pady=10, padx=18, highlightthickness=1, highlightbackground="#e2e7ec")
        header.pack(fill="x", side="top")

        # Left: Title & Subtitle
        title_frame = tk.Frame(header, bg="#ffffff")
        title_frame.pack(side="left")

        lbl_axis = tk.Label(
            title_frame,
            text="AXIS",
            font=("Helvetica", 14, "bold"),
            fg="#1e242b",
            bg="#ffffff"
        )
        lbl_axis.pack(side="left")

        lbl_bar = tk.Label(
            title_frame,
            text=" | Evergreen groceries - RF Sensing VMS",
            font=("Helvetica", 11, "bold"),
            fg="#5c6b7d",
            bg="#ffffff"
        )
        lbl_bar.pack(side="left")

        # Right Header: Controls
        ctrl_frame = tk.Frame(header, bg="#ffffff")
        ctrl_frame.pack(side="right")

        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(ctrl_frame, textvariable=self.port_var, width=12)
        self._refresh_ports()
        self.combo_ports.pack(side="left", padx=6)

        btn_connect = tk.Button(
            ctrl_frame,
            text="⚡ CONNECT",
            command=self._toggle_connection,
            bg="#1e242b",
            fg="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        btn_connect.pack(side="left", padx=6)
        self.btn_connect = btn_connect

        btn_demo = tk.Button(
            ctrl_frame,
            text="🎮 DEMO MODE",
            command=self._toggle_demo,
            bg="#fdb813",
            fg="#1e242b",
            font=("Helvetica", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        btn_demo.pack(side="left", padx=6)
        self.btn_demo = btn_demo

        # 2. Main Body Layout
        body = tk.Frame(self, bg="#edf1f5")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        # Left: Clean Light Polar Radar / Floorplan Screen
        left_frame = tk.Frame(body, bg="#ffffff", bd=1, relief="solid", highlightthickness=0)
        left_frame.configure(highlightbackground="#e2e7ec")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        lbl_radar_title = tk.Label(
            left_frame,
            text="FRESNEL MULTIPATH COVERAGE MATRIX (2.4 GHz)",
            font=("Helvetica", 10, "bold"),
            fg="#1e242b",
            bg="#ffffff",
            pady=8
        )
        lbl_radar_title.pack(side="top", anchor="w", padx=12)

        self.canvas_radar = tk.Canvas(
            left_frame, width=460, height=440, bg="#ffffff", highlightthickness=0
        )
        self.canvas_radar.pack(fill="both", expand=True, padx=10, pady=10)

        # Right: KPI and Waveform Frame
        right_frame = tk.Frame(body, bg="#edf1f5")
        right_frame.pack(side="right", fill="both", expand=True)

        # KPI Badges Card
        kpi_frame = tk.Frame(right_frame, bg="#ffffff", bd=1, relief="solid", pady=12, padx=16)
        kpi_frame.configure(highlightbackground="#e2e7ec")
        kpi_frame.pack(fill="x", pady=(0, 12))

        self.lbl_motion = tk.Label(
            kpi_frame, text="MOTION SCORE: 0.00", font=("Helvetica", 12, "bold"), fg="#0096d6", bg="#ffffff"
        )
        self.lbl_motion.pack(anchor="w", pady=2)

        self.lbl_thresh = tk.Label(
            kpi_frame, text="THRESHOLD: 25.00", font=("Helvetica", 11), fg="#f39c12", bg="#ffffff"
        )
        self.lbl_thresh.pack(anchor="w", pady=2)

        self.lbl_status = tk.Label(
            kpi_frame, text="STATUS: ROOM SECURE // BASELINE NORMAL", font=("Helvetica", 11, "bold"), fg="#27ae60", bg="#ffffff"
        )
        self.lbl_status.pack(anchor="w", pady=2)

        # Oscilloscope Waveform Card
        wave_frame = tk.Frame(right_frame, bg="#ffffff", bd=1, relief="solid", pady=10, padx=12)
        wave_frame.configure(highlightbackground="#e2e7ec")
        wave_frame.pack(fill="both", expand=True)

        lbl_wave_title = tk.Label(
            wave_frame,
            text="REAL-TIME MOTION ENERGY OSCILLOSCOPE",
            font=("Helvetica", 10, "bold"),
            fg="#1e242b",
            bg="#ffffff"
        )
        lbl_wave_title.pack(side="top", anchor="w", padx=4, pady=4)

        self.canvas_wave = tk.Canvas(
            wave_frame, height=220, bg="#ffffff", highlightthickness=1, highlightbackground="#eaedf2"
        )
        self.canvas_wave.pack(fill="both", expand=True, pady=6)

        # 3. Footer Bar
        footer = tk.Frame(self, bg="#1e242b", pady=6, padx=16)
        footer.pack(fill="x", side="bottom")

        self.lbl_footer = tk.Label(
            footer, text="SERIAL PORT: DISCONNECTED - Select COM Port or Launch Demo", font=("Helvetica", 9), fg="#cbd5e1", bg="#1e242b"
        )
        self.lbl_footer.pack(side="left")

        lbl_copy = tk.Label(
            footer, text="AXIS COMMUNICATIONS // RF MULTIPATH VMS", font=("Helvetica", 9), fg="#94a3b8", bg="#1e242b"
        )
        lbl_copy.pack(side="right")

    def _refresh_ports(self):
        if SERIAL_AVAILABLE:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.combo_ports["values"] = ports
            if ports:
                self.combo_ports.current(0)
        else:
            self.combo_ports["values"] = ["No pyserial"]

    def _toggle_demo(self):
        self.demo_mode = not self.demo_mode
        if self.demo_mode:
            self.btn_demo.config(text="STOP DEMO", bg="#e74c3c", fg="#ffffff")
            self.lbl_status.config(text="STATUS: SIMULATION DEMO (WALKING)", fg="#0096d6")
            self.lbl_footer.config(text="DEMO MODE ACTIVE - Simulating 2.4 GHz Multipath Scattering")
        else:
            self.btn_demo.config(text="🎮 DEMO MODE", bg="#fdb813", fg="#1e242b")
            self.lbl_status.config(text="STATUS: STANDBY", fg="#5c6b7d")
            self.lbl_footer.config(text="SERIAL PORT: DISCONNECTED")

    def _toggle_connection(self):
        if self.is_running:
            self.is_running = False
            if self.ser:
                self.ser.close()
            self.btn_connect.config(text="⚡ CONNECT", bg="#1e242b", fg="#ffffff")
            self.lbl_footer.config(text="SERIAL PORT: DISCONNECTED")
            return

        port = self.port_var.get()
        if not port or port == "No pyserial":
            messagebox.showerror("Error", "Please select a valid COM port. Make sure pyserial is installed.")
            return

        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            self.is_running = True
            self.btn_connect.config(text="DISCONNECT", bg="#e74c3c", fg="#ffffff")
            self.lbl_footer.config(text=f"CONNECTED TO {port} (115200 BAUD)")

            thread = threading.Thread(target=self._serial_worker, daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("Serial Connection Error", str(e))

    def _serial_worker(self):
        while self.is_running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if "Motion_Score" in line:
                    parts = line.split()
                    for p in parts:
                        if ":" in p:
                            k, v = p.split(":", 1)
                            if k == "Motion_Score":
                                self.motion_score = float(v)
                            elif k == "Threshold":
                                self.threshold = float(v)
                            elif k == "Alert":
                                self.is_alert = (int(v) > 0)
            except Exception:
                break

    def _animate(self):
        if self.demo_mode:
            t = time.time()
            is_walking = (int(t) % 6 > 3)
            self.motion_score = 4.0 + (28.0 if is_walking else 0.0) + (math.sin(t * 8) * 2.5)
            self.threshold = 18.0
            self.is_alert = (self.motion_score > self.threshold)

        self.motion_history.append(self.motion_score)
        self.motion_history.pop(0)
        self.threshold_history.append(self.threshold)
        self.threshold_history.pop(0)

        self.lbl_motion.config(text=f"MOTION SCORE: {self.motion_score:.2f}")
        self.lbl_thresh.config(text=f"THRESHOLD: {self.threshold:.2f}")

        if self.is_alert:
            self.lbl_status.config(text="🚨 INTRUSION DETECTED // FRESNEL BREACH", fg="#e74c3c")
            if len(self.blips) < 6:
                self.blips.append([self.sweep_angle, 0.4 + 0.3 * (math.sin(time.time())), 1.0])
        elif self.is_running or self.demo_mode:
            self.lbl_status.config(text="🛡️ ROOM SECURE // BASELINE NORMAL", fg="#27ae60")

        # 1. Draw Radar
        self.canvas_radar.delete("all")
        cw = self.canvas_radar.winfo_width() or 460
        ch = self.canvas_radar.winfo_height() or 440
        cx, cy = cw // 2, ch // 2
        r = min(cx, cy) - 20

        # Light Theme Grid & Rings
        for scale in [0.25, 0.5, 0.75, 1.0]:
            cr = r * scale
            self.canvas_radar.create_oval(cx - cr, cy - cr, cx + cr, cy + cr, outline="#d1d9e2", width=1)

        # Crosshairs
        self.canvas_radar.create_line(cx - r, cy, cx + r, cy, fill="#e2e8f0")
        self.canvas_radar.create_line(cx, cy - r, cx, cy + r, fill="#e2e8f0")

        # Field of View Cones (Axis Style)
        # Blue Cones down aisles
        self.canvas_radar.create_polygon(cx, cy, cx - 70, cy - r, cx + 70, cy - r, fill="#e0f2fe", outline="#0096d6")
        # Green Panoramic Sector at bottom
        self.canvas_radar.create_arc(cx - r*0.7, cy - r*0.7, cx + r*0.7, cy + r*0.7, start=220, extent=100, fill="#ecfccb", outline="#85bb2f")

        # Echo Target Blips
        for b in list(self.blips):
            ang, radius, intensity = b
            bx = cx + math.cos(ang) * (r * radius)
            by = cy + math.sin(ang) * (r * radius)
            sz = 7 * intensity
            self.canvas_radar.create_oval(bx - sz, by - sz, bx + sz, by + sz, fill="#e74c3c", outline="")
            b[2] -= 0.03
            if b[2] <= 0:
                self.blips.remove(b)

        # Sweep Line
        sx = cx + math.cos(self.sweep_angle) * r
        sy = cy + math.sin(self.sweep_angle) * r
        self.canvas_radar.create_line(cx, cy, sx, sy, fill="#0096d6", width=2)
        self.sweep_angle = (self.sweep_angle + 0.04) % (math.pi * 2)

        # 2. Draw Waveform
        self.canvas_wave.delete("all")
        ww = self.canvas_wave.winfo_width() or 400
        wh = self.canvas_wave.winfo_height() or 220

        # Grid lines
        for y_frac in [0.25, 0.5, 0.75]:
            gy = wh * y_frac
            self.canvas_wave.create_line(0, gy, ww, gy, fill="#f1f5f9")

        step_x = ww / (self.history_len - 1)
        max_y = max(50.0, self.threshold * 1.8)

        # Threshold line
        pts_th = []
        for i, val in enumerate(self.threshold_history):
            x = i * step_x
            y = wh - (min(max_y, val) / max_y) * (wh - 20) - 10
            pts_th.extend([x, y])
        if len(pts_th) >= 4:
            self.canvas_wave.create_line(*pts_th, fill="#f39c12", width=2, dash=(4, 2))

        # Motion line
        pts_m = []
        for i, val in enumerate(self.motion_history):
            x = i * step_x
            y = wh - (min(max_y, val) / max_y) * (wh - 20) - 10
            pts_m.extend([x, y])
        if len(pts_m) >= 4:
            col = "#e74c3c" if self.is_alert else "#0096d6"
            self.canvas_wave.create_line(*pts_m, fill=col, width=2)

        self.after(35, self._animate)


if __name__ == "__main__":
    app = AxisRadarDesktopApp()
    app.mainloop()

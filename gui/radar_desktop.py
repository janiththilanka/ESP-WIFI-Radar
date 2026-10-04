"""
=====================================================================================
 RF·CSI Sensing Deck — Standalone Python Desktop HUD (v2.2)
 Next-Gen Volumetric Wi-Fi Radar & Precision DSP Telemetry Console
 (ESP32 + ESP8266 Link)
=====================================================================================
 Requirements:
   pip install pyserial
 Usage:
   python gui/radar_desktop.py [COM_PORT]
=====================================================================================
"""

import sys
import math
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


# Unified Visual Palette
THEME = {
    "bg_main": "#edf1f5",
    "bg_card": "#ffffff",
    "bg_subtle": "#f8fafc",
    "border": "#e2e7ec",
    "text_primary": "#1e242b",
    "text_muted": "#64748b",
    "text_accent": "#0284c7",
    "score_color": "#0284c7",
    "limit_color": "#d97706",
    "baseline_color": "#475569",
    "alert_bg": "#fef2f2",
    "alert_border": "#ef4444",
    "alert_text": "#b91c1c",
    "ok_bg": "#f0fdf4",
    "ok_border": "#22c55e",
    "ok_text": "#15803d",
    "radar_bg": "#ffffff",
    "radar_grid": "#d1d9e2",
    "radar_sweep": "#0284c7",
    "radar_blip": "#ef4444",
    "spectrum_bar": "#0284c7",
    "spectrum_bg": "#f8fafc",
    "wave_bg": "#ffffff",
    "wave_grid": "#f1f5f9",
    "header_bg": "#ffffff",
    "footer_bg": "#1e242b",
    "footer_text": "#94a3b8",
    "btn_primary_bg": "#0284c7",
    "btn_primary_fg": "#ffffff",
}


class RadarDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RF·CSI Sensing Deck — 2.4 GHz Multipath Detection Console")
        self.geometry("1180x820")
        self.minsize(1040, 720)

        self.theme = THEME

        # Telemetry State
        self.motion_score = 0.0
        self.threshold = 12.0
        self.baseline = 3.5
        self.is_alert = False
        self.beacon_connected = False
        self.beacon_rssi = -60
        self.beacon_rate = 0.0
        self.beacon_mac = "SEARCHING"
        self.subcarrier_variance = 0.0

        # Subcarriers (52 802.11n OFDM channels)
        self.num_subcarriers = 52
        self.subcarriers = [0.0] * self.num_subcarriers

        # Visual Radar State
        self.sweep_angle = 0.0
        self.blips = []  # list of [angle, radius, intensity]

        # Waveform History
        self.history_len = 120
        self.motion_history = [0.0] * self.history_len
        self.threshold_history = [12.0] * self.history_len
        self.baseline_history = [3.5] * self.history_len

        # Calibration state
        self.is_calibrating = False
        self.cal_countdown = 5

        # Serial Thread State
        self.ser = None
        self.is_running = False
        self.demo_mode = False

        self._build_ui()
        self._refresh_ports()
        self._animate()

    def _build_ui(self):
        self.configure(bg=self.theme["bg_main"])

        # ====================================================================
        # 1. TOP NAVIGATION & BRANDING BAR
        # ====================================================================
        self.header_frame = tk.Frame(
            self, bg=self.theme["header_bg"], bd=0, pady=8, padx=16,
            highlightthickness=1, highlightbackground=self.theme["border"]
        )
        self.header_frame.pack(fill="x", side="top")

        # Left: Brand Icon + Title
        brand_frame = tk.Frame(self.header_frame, bg=self.theme["header_bg"])
        brand_frame.pack(side="left")

        self.lbl_brand_icon = tk.Label(
            brand_frame, text="📡", font=("Segoe UI Emoji", 16),
            bg=self.theme["header_bg"]
        )
        self.lbl_brand_icon.pack(side="left", padx=(0, 8))

        brand_text_box = tk.Frame(brand_frame, bg=self.theme["header_bg"])
        brand_text_box.pack(side="left")

        self.lbl_title = tk.Label(
            brand_text_box, text="RF·CSI SENSING DECK",
            font=("Helvetica", 13, "bold"), fg=self.theme["text_primary"],
            bg=self.theme["header_bg"]
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_sub = tk.Label(
            brand_text_box, text="2.4 GHz Multipath Radar · ESP32 + ESP8266 Link",
            font=("Helvetica", 9), fg=self.theme["text_muted"],
            bg=self.theme["header_bg"]
        )
        self.lbl_sub.pack(anchor="w")

        # Center: Beacon Capsule Pill
        self.beacon_pill = tk.Frame(
            self.header_frame, bg=self.theme["bg_subtle"],
            highlightthickness=1, highlightbackground=self.theme["border"],
            padx=12, pady=4
        )
        self.beacon_pill.pack(side="left", padx=25)

        self.lbl_bcn_dot = tk.Label(
            self.beacon_pill, text="●", font=("Helvetica", 11, "bold"),
            fg="#94a3b8", bg=self.theme["bg_subtle"]
        )
        self.lbl_bcn_dot.pack(side="left", padx=(0, 6))

        bcn_box = tk.Frame(self.beacon_pill, bg=self.theme["bg_subtle"])
        bcn_box.pack(side="left")

        self.lbl_bcn_title = tk.Label(
            bcn_box, text="BEACON: SEARCHING...", font=("Helvetica", 9, "bold"),
            fg=self.theme["text_muted"], bg=self.theme["bg_subtle"]
        )
        self.lbl_bcn_title.pack(anchor="w")

        self.lbl_bcn_detail = tk.Label(
            bcn_box, text="-- dBm · 0 PPS · --:--:--:--:--:--",
            font=("Consolas", 8), fg=self.theme["text_muted"],
            bg=self.theme["bg_subtle"]
        )
        self.lbl_bcn_detail.pack(anchor="w")

        # Right: Port Selection & Action Buttons
        ctrl_frame = tk.Frame(self.header_frame, bg=self.theme["header_bg"])
        ctrl_frame.pack(side="right")

        self.port_var = tk.StringVar()
        self.combo_ports = ttk.Combobox(ctrl_frame, textvariable=self.port_var, width=11, state="readonly")
        self.combo_ports.pack(side="left", padx=4)

        self.btn_refresh = tk.Button(
            ctrl_frame, text="🔄", command=self._refresh_ports,
            font=("Helvetica", 9), relief="flat", cursor="hand2", padx=4, pady=3,
            bg=self.theme["bg_subtle"], fg=self.theme["text_primary"]
        )
        self.btn_refresh.pack(side="left", padx=2)

        self.btn_connect = tk.Button(
            ctrl_frame, text="⚡ CONNECT", command=self._toggle_connection,
            bg=self.theme["btn_primary_bg"], fg=self.theme["btn_primary_fg"],
            font=("Helvetica", 9, "bold"), relief="flat", padx=12, pady=4, cursor="hand2"
        )
        self.btn_connect.pack(side="left", padx=5)

        self.btn_cal = tk.Button(
            ctrl_frame, text="🎯 CALIBRATE", command=self._start_calibration,
            bg=self.theme["bg_subtle"], fg=self.theme["text_primary"],
            font=("Helvetica", 9, "bold"), relief="flat", padx=10, pady=4, cursor="hand2"
        )
        self.btn_cal.pack(side="left", padx=4)

        self.btn_demo = tk.Button(
            ctrl_frame, text="🎮 DEMO", command=self._toggle_demo,
            bg="#f59e0b", fg="#ffffff",
            font=("Helvetica", 9, "bold"), relief="flat", padx=10, pady=4, cursor="hand2"
        )
        self.btn_demo.pack(side="left", padx=4)

        # ====================================================================
        # 2. DYNAMIC STATUS & TELEMETRY STRIP
        # ====================================================================
        self.status_strip = tk.Frame(
            self, bg=self.theme["ok_bg"], bd=0, padx=16, pady=10,
            highlightthickness=1, highlightbackground=self.theme["ok_border"]
        )
        self.status_strip.pack(fill="x", padx=16, pady=(10, 6))

        strip_left = tk.Frame(self.status_strip, bg=self.theme["ok_bg"])
        strip_left.pack(side="left", fill="both", expand=True)

        self.lbl_status_icon = tk.Label(
            strip_left, text="🛡️", font=("Segoe UI Emoji", 20),
            bg=self.theme["ok_bg"]
        )
        self.lbl_status_icon.pack(side="left", padx=(0, 10))

        status_text_box = tk.Frame(strip_left, bg=self.theme["ok_bg"])
        status_text_box.pack(side="left")

        self.lbl_status_head = tk.Label(
            status_text_box, text="ROOM SECURE — ZERO ANOMALIES",
            font=("Helvetica", 12, "bold"), fg=self.theme["ok_text"],
            bg=self.theme["ok_bg"]
        )
        self.lbl_status_head.pack(anchor="w")

        self.lbl_status_desc = tk.Label(
            status_text_box,
            text="Fresnel reflection matrix is stationary. RF perturbation within ambient noise limit.",
            font=("Helvetica", 9), fg=self.theme["text_muted"],
            bg=self.theme["ok_bg"]
        )
        self.lbl_status_desc.pack(anchor="w")

        # Metric Pills inside status strip
        strip_right = tk.Frame(self.status_strip, bg=self.theme["ok_bg"])
        strip_right.pack(side="right")

        def make_metric(parent, label_text, default_val, fg_color):
            box = tk.Frame(parent, bg=self.theme["bg_card"], padx=12, pady=4,
                           highlightthickness=1, highlightbackground=self.theme["border"])
            box.pack(side="left", padx=4)
            lbl = tk.Label(box, text=label_text, font=("Helvetica", 8, "bold"),
                           fg=self.theme["text_muted"], bg=self.theme["bg_card"])
            lbl.pack(anchor="center")
            val = tk.Label(box, text=default_val, font=("Consolas", 13, "bold"),
                           fg=fg_color, bg=self.theme["bg_card"])
            val.pack(anchor="center")
            return val

        self.val_motion = make_metric(strip_right, "PERTURBATION", "0.00", self.theme["score_color"])
        self.val_thresh = make_metric(strip_right, "THRESHOLD", "12.00", self.theme["limit_color"])
        self.val_floor  = make_metric(strip_right, "BASELINE", "3.50", self.theme["baseline_color"])
        self.val_margin = make_metric(strip_right, "MARGIN", "-- dBm", self.theme["text_accent"])

        # ====================================================================
        # 3. MAIN WORKSPACE (2 EQUAL COLUMNS)
        # ====================================================================
        body = tk.Frame(self, bg=self.theme["bg_main"])
        body.pack(fill="both", expand=True, padx=16, pady=6)

        # ----------------- LEFT COLUMN: Visual Radar & OFDM Spectrum -----------------
        left_col = tk.Frame(body, bg=self.theme["bg_main"])
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Card 1: Polar Radar Canvas
        self.radar_card = tk.Frame(
            left_col, bg=self.theme["bg_card"], bd=0, padx=12, pady=8,
            highlightthickness=1, highlightbackground=self.theme["border"]
        )
        self.radar_card.pack(fill="both", expand=True, pady=(0, 6))

        lbl_radar = tk.Label(
            self.radar_card, text="FRESNEL MULTIPATH COVERAGE MATRIX (2.4 GHz)",
            font=("Helvetica", 10, "bold"), fg=self.theme["text_primary"],
            bg=self.theme["bg_card"]
        )
        lbl_radar.pack(anchor="w", pady=(0, 4))

        self.canvas_radar = tk.Canvas(
            self.radar_card, height=270, bg=self.theme["radar_bg"], highlightthickness=0
        )
        self.canvas_radar.pack(fill="both", expand=True)

        # Card 2: 52-Channel OFDM Subcarrier Heatmap
        self.spectrum_card = tk.Frame(
            left_col, bg=self.theme["bg_card"], bd=0, padx=12, pady=8,
            highlightthickness=1, highlightbackground=self.theme["border"]
        )
        self.spectrum_card.pack(fill="x", pady=(0, 0))

        lbl_spec = tk.Label(
            self.spectrum_card, text="52-CHANNEL OFDM SUBCARRIER JITTER SPECTRUM (-26 to +26)",
            font=("Helvetica", 9, "bold"), fg=self.theme["text_primary"],
            bg=self.theme["bg_card"]
        )
        lbl_spec.pack(anchor="w", pady=(0, 4))

        self.canvas_spectrum = tk.Canvas(
            self.spectrum_card, height=110, bg=self.theme["spectrum_bg"], highlightthickness=0
        )
        self.canvas_spectrum.pack(fill="x")

        # ----------------- RIGHT COLUMN: Oscilloscope, Calibrator, Audit -----------------
        right_col = tk.Frame(body, bg=self.theme["bg_main"])
        right_col.pack(side="right", fill="both", expand=True, padx=(6, 0))

        # Card 3: Oscilloscope Canvas
        self.wave_card = tk.Frame(
            right_col, bg=self.theme["bg_card"], bd=0, padx=12, pady=8,
            highlightthickness=1, highlightbackground=self.theme["border"]
        )
        self.wave_card.pack(fill="both", expand=True, pady=(0, 6))

        wave_head = tk.Frame(self.wave_card, bg=self.theme["bg_card"])
        wave_head.pack(fill="x", pady=(0, 4))

        lbl_wave = tk.Label(
            wave_head, text="REAL-TIME MOTION ENERGY OSCILLOSCOPE (25 Hz)",
            font=("Helvetica", 10, "bold"), fg=self.theme["text_primary"],
            bg=self.theme["bg_card"]
        )
        lbl_wave.pack(side="left")

        # Waveform Legend
        leg_frame = tk.Frame(wave_head, bg=self.theme["bg_card"])
        leg_frame.pack(side="right")

        tk.Label(leg_frame, text="— MOT", font=("Helvetica", 8, "bold"), fg=self.theme["score_color"], bg=self.theme["bg_card"]).pack(side="left", padx=4)
        tk.Label(leg_frame, text="--- LIM", font=("Helvetica", 8, "bold"), fg=self.theme["limit_color"], bg=self.theme["bg_card"]).pack(side="left", padx=4)
        tk.Label(leg_frame, text="... FLR", font=("Helvetica", 8, "bold"), fg=self.theme["baseline_color"], bg=self.theme["bg_card"]).pack(side="left", padx=4)

        self.canvas_wave = tk.Canvas(
            self.wave_card, height=180, bg=self.theme["wave_bg"], highlightthickness=0
        )
        self.canvas_wave.pack(fill="both", expand=True)

        # Card 4: Precision DSP Calibrator & Quick Presets
        self.cal_card = tk.Frame(
            right_col, bg=self.theme["bg_card"], bd=0, padx=12, pady=8,
            highlightthickness=1, highlightbackground=self.theme["border"]
        )
        self.cal_card.pack(fill="x", pady=(0, 6))

        lbl_cal_title = tk.Label(
            self.cal_card, text="PRECISION DSP TUNING CONSOLE & QUICK PRESETS",
            font=("Helvetica", 9, "bold"), fg=self.theme["text_primary"],
            bg=self.theme["bg_card"]
        )
        lbl_cal_title.pack(anchor="w", pady=(0, 4))

        # Quick Preset Buttons
        preset_row = tk.Frame(self.cal_card, bg=self.theme["bg_card"])
        preset_row.pack(fill="x", pady=(0, 6))

        def make_preset_btn(text, s_val, o_val, g_val):
            return tk.Button(
                preset_row, text=text, font=("Helvetica", 8, "bold"),
                relief="flat", bg=self.theme["bg_subtle"], fg=self.theme["text_primary"],
                padx=8, pady=3, cursor="hand2",
                command=lambda: self._apply_preset(s_val, o_val, g_val)
            )

        make_preset_btn("🫁 Micro-Presence", 1.8, 3.0, 1.5).pack(side="left", padx=2)
        make_preset_btn("👤 Balanced", 2.2, 4.5, 1.0).pack(side="left", padx=2)
        make_preset_btn("🏃 Walking Alarm", 3.5, 8.0, 0.8).pack(side="left", padx=2)
        make_preset_btn("🐾 Pet Immune", 4.5, 12.0, 0.6).pack(side="left", padx=2)

        # Sliders Row
        sliders_frame = tk.Frame(self.cal_card, bg=self.theme["bg_card"])
        sliders_frame.pack(fill="x")

        # Slider 1: Sensitivity
        s_box = tk.Frame(sliders_frame, bg=self.theme["bg_card"])
        s_box.pack(side="left", fill="x", expand=True, padx=4)
        self.lbl_sens_val = tk.Label(s_box, text="Sensitivity: 2.2x", font=("Helvetica", 8), bg=self.theme["bg_card"], fg=self.theme["text_muted"])
        self.lbl_sens_val.pack(anchor="w")
        self.slider_sens = ttk.Scale(s_box, from_=1.0, to=10.0, value=2.2, command=self._on_sens_change)
        self.slider_sens.pack(fill="x")

        # Slider 2: Noise Margin Offset
        o_box = tk.Frame(sliders_frame, bg=self.theme["bg_card"])
        o_box.pack(side="left", fill="x", expand=True, padx=4)
        self.lbl_offs_val = tk.Label(o_box, text="Offset Margin: 4.5", font=("Helvetica", 8), bg=self.theme["bg_card"], fg=self.theme["text_muted"])
        self.lbl_offs_val.pack(anchor="w")
        self.slider_offs = ttk.Scale(o_box, from_=0.5, to=25.0, value=4.5, command=self._on_offs_change)
        self.slider_offs.pack(fill="x")

        # Slider 3: Motion Pre-Amp Gain
        g_box = tk.Frame(sliders_frame, bg=self.theme["bg_card"])
        g_box.pack(side="left", fill="x", expand=True, padx=4)
        self.lbl_gain_val = tk.Label(g_box, text="Pre-Amp Gain: 1.0x", font=("Helvetica", 8), bg=self.theme["bg_card"], fg=self.theme["text_muted"])
        self.lbl_gain_val.pack(anchor="w")
        self.slider_gain = ttk.Scale(g_box, from_=0.2, to=4.0, value=1.0, command=self._on_gain_change)
        self.slider_gain.pack(fill="x")

        # Card 5: Security Event Audit Log
        self.log_card = tk.Frame(
            right_col, bg=self.theme["bg_card"], bd=0, padx=12, pady=6,
            highlightthickness=1, highlightbackground=self.theme["border"]
        )
        self.log_card.pack(fill="x")

        lbl_log = tk.Label(
            self.log_card, text="SECURITY AUDIT EVENT STREAM",
            font=("Helvetica", 9, "bold"), fg=self.theme["text_primary"],
            bg=self.theme["bg_card"]
        )
        lbl_log.pack(anchor="w", pady=(0, 2))

        self.log_list = tk.Listbox(
            self.log_card, height=4, font=("Consolas", 8),
            bg=self.theme["bg_subtle"], fg=self.theme["text_primary"],
            highlightthickness=0, bd=0
        )
        self.log_list.pack(fill="x")
        self._add_log("SYSTEM: RF·CSI Sensing Console initialized (115200 baud).")

        # ====================================================================
        # 4. FOOTER STATUS BAR
        # ====================================================================
        self.footer = tk.Frame(self, bg=self.theme["footer_bg"], pady=4, padx=16)
        self.footer.pack(fill="x", side="bottom")

        self.lbl_footer = tk.Label(
            self.footer, text="PORT: DISCONNECTED — Select COM Port or Launch Demo Mode",
            font=("Helvetica", 8), fg=self.theme["footer_text"], bg=self.theme["footer_bg"]
        )
        self.lbl_footer.pack(side="left")

        self.lbl_copy = tk.Label(
            self.footer, text="RF·CSI SENSING DECK // 2.4 GHz MULTIPATH RADAR v2.2",
            font=("Helvetica", 8), fg=self.theme["footer_text"], bg=self.theme["footer_bg"]
        )
        self.lbl_copy.pack(side="right")

    # ====================================================================
    # SERIAL & TELEMETRY HANDLING
    # ====================================================================
    def _refresh_ports(self):
        if SERIAL_AVAILABLE:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.combo_ports["values"] = ports
            if ports:
                self.combo_ports.current(0)
        else:
            self.combo_ports["values"] = ["No pyserial"]

    def _toggle_connection(self):
        if self.is_running:
            self.is_running = False
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.btn_connect.config(text="⚡ CONNECT", bg=self.theme["btn_primary_bg"], fg=self.theme["btn_primary_fg"])
            self.lbl_footer.config(text="PORT: DISCONNECTED")
            self._add_log("SERIAL: Disconnected.")
            return

        port = self.port_var.get()
        if not port or port == "No pyserial":
            messagebox.showerror("Serial Error", "Please select a valid COM port.\n(Verify ESP32 is plugged in and drivers installed).")
            return

        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            self.is_running = True
            self.btn_connect.config(text="DISCONNECT", bg="#dc2626", fg="#ffffff")
            self.lbl_footer.config(text=f"CONNECTED TO {port} @ 115200 BAUD")
            self._add_log(f"SERIAL: Connected to {port} @ 115200 baud.")

            thread = threading.Thread(target=self._serial_worker, daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("Connection Failed", str(e))

    def _serial_worker(self):
        while self.is_running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if "Motion_Score:" in line:
                    parts = line.split()
                    for p in parts:
                        if ":" in p:
                            k, v = p.split(":", 1)
                            if k == "Motion_Score":
                                self.motion_score = float(v)
                            elif k == "Threshold":
                                self.threshold = float(v)
                            elif k == "Alert":
                                new_alert = (int(v) > 0)
                                if new_alert and not self.is_alert:
                                    self._add_log(f"ALERT: Intrusion detected (Score: {self.motion_score:.1f} > Limit: {self.threshold:.1f})")
                                elif not new_alert and self.is_alert:
                                    self._add_log("STATUS: Perimeter restored (ROOM SECURE).")
                                self.is_alert = new_alert
                            elif k == "Baseline":
                                self.baseline = float(v)
                            elif k == "Beacon_Status":
                                self.beacon_connected = (int(v) > 0)
                            elif k == "Beacon_RSSI":
                                self.beacon_rssi = int(v)
                            elif k == "Beacon_Rate":
                                self.beacon_rate = float(v)
                            elif k == "Beacon_MAC":
                                self.beacon_mac = v
                            elif k == "SubVar":
                                self.subcarrier_variance = float(v)

                elif "[CAL_COMPLETE]" in line:
                    self._add_log(f"CALIBRATION: {line}")
            except Exception:
                break

    def _send_command(self, cmd_str):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd_str + "\n").encode("utf-8"))
                self._add_log(f"TX CMD: {cmd_str}")
            except Exception as e:
                self._add_log(f"TX ERROR: {e}")

    # ====================================================================
    # CALIBRATION & PRESETS
    # ====================================================================
    def _start_calibration(self):
        self._send_command("CMD:CALIBRATE")
        self.is_calibrating = True
        self.cal_countdown = 5
        self._add_log("CALIBRATE: Initiating 5s ambient RF baseline recording...")

    def _apply_preset(self, s, o, g):
        self.slider_sens.set(s)
        self.slider_offs.set(o)
        self.slider_gain.set(g)
        self._on_sens_change(s)
        self._on_offs_change(o)
        self._on_gain_change(g)
        self._add_log(f"PRESET: Applied SENS={s:.1f}, OFFS={o:.1f}, GAIN={g:.1f}")

    def _on_sens_change(self, val):
        v = float(val)
        self.lbl_sens_val.config(text=f"Sensitivity: {v:.1f}x")
        self._send_command(f"CMD:SENS:{v:.1f}")

    def _on_offs_change(self, val):
        v = float(val)
        self.lbl_offs_val.config(text=f"Offset Margin: {v:.1f}")
        self._send_command(f"CMD:OFFS:{v:.1f}")

    def _on_gain_change(self, val):
        v = float(val)
        self.lbl_gain_val.config(text=f"Pre-Amp Gain: {v:.1f}x")
        self._send_command(f"CMD:GAIN:{v:.1f}")

    def _add_log(self, text):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {text}"
        self.log_list.insert(0, entry)
        if self.log_list.size() > 50:
            self.log_list.delete(50, "end")

    def _toggle_demo(self):
        self.demo_mode = not self.demo_mode
        if self.demo_mode:
            self.btn_demo.config(text="STOP DEMO", bg="#dc2626")
            self.lbl_footer.config(text="DEMO MODE ACTIVE — Simulating 2.4 GHz Fresnel Multipath Perturbations")
            self.beacon_connected = True
            self.beacon_rssi = -62
            self.beacon_rate = 34.0
            self.beacon_mac = "84:CC:A8:81:E1:BB"
            self._add_log("DEMO: Synthetic RF multipath simulation enabled.")
        else:
            self.btn_demo.config(text="🎮 DEMO", bg="#f59e0b")
            self.lbl_footer.config(text="PORT: DISCONNECTED")
            self.beacon_connected = False
            self.beacon_rssi = -90
            self.beacon_rate = 0.0
            self.beacon_mac = "SEARCHING"
            self._add_log("DEMO: Simulation ended.")

    # ====================================================================
    # 4. MAIN ANIMATION & CANVAS RENDERING (25 FPS)
    # ====================================================================
    def _animate(self):
        t = time.time()

        # Synthetic demo data generator
        if self.demo_mode:
            walking_phase = (int(t) % 8 >= 4)
            if walking_phase:
                self.motion_score = 14.0 + math.sin(t * 7) * 8.0 + (math.cos(t * 19) * 3.0)
            else:
                self.motion_score = 1.8 + math.sin(t * 2) * 1.1

            self.threshold = 10.5
            self.baseline = 2.8
            self.is_alert = (self.motion_score > self.threshold)
            self.beacon_rssi = -60 + int(math.sin(t) * 3)

        # Update History Buffers
        self.motion_history.append(self.motion_score)
        self.motion_history.pop(0)
        self.threshold_history.append(self.threshold)
        self.threshold_history.pop(0)
        self.baseline_history.append(self.baseline)
        self.baseline_history.pop(0)

        # Update KPI values
        self.val_motion.config(text=f"{self.motion_score:5.2f}")
        self.val_thresh.config(text=f"{self.threshold:5.2f}")
        self.val_floor.config(text=f"{self.baseline:5.2f}")
        self.val_margin.config(text=f"{self.beacon_rssi} dBm")

        # Update Beacon Capsule
        if self.beacon_connected:
            self.lbl_bcn_dot.config(text="●", fg="#22c55e")
            self.lbl_bcn_title.config(text="BEACON: ONLINE", fg=self.theme["text_primary"])
            self.lbl_bcn_detail.config(text=f"{self.beacon_rssi} dBm · {self.beacon_rate:.0f} PPS · {self.beacon_mac}")
        else:
            self.lbl_bcn_dot.config(text="●", fg="#f59e0b")
            self.lbl_bcn_title.config(text="BEACON: SEARCHING...", fg=self.theme["text_muted"])
            self.lbl_bcn_detail.config(text="-- dBm · 0 PPS · SEARCHING")

        # Update Status Banner
        if not self.beacon_connected and not self.demo_mode:
            self.status_strip.config(bg="#f8fafc", highlightbackground="#cbd5e1")
            self.lbl_status_icon.config(text="📡", bg="#f8fafc")
            self.lbl_status_head.config(text="BEACON OFFLINE — WAITING FOR RF SIGNAL", fg="#64748b", bg="#f8fafc")
            self.lbl_status_desc.config(text="Transmitter beacon is offline or outside RF range. Power on ESP8266 node.", bg="#f8fafc")
        elif self.is_alert:
            self.status_strip.config(bg=self.theme["alert_bg"], highlightbackground=self.theme["alert_border"])
            self.lbl_status_icon.config(text="🚨", bg=self.theme["alert_bg"])
            self.lbl_status_head.config(text="! INTRUSION DETECTED ! — FRESNEL FIELD BREACH", fg=self.theme["alert_text"], bg=self.theme["alert_bg"])
            self.lbl_status_desc.config(text="Significant 2.4 GHz multipath perturbation detected. Motion energy exceeded dynamic threshold.", bg=self.theme["alert_bg"])
            if len(self.blips) < 8:
                self.blips.append([self.sweep_angle, 0.4 + 0.35 * math.sin(t * 3), 1.0])
        elif self.motion_score > (self.baseline * 1.35):
            self.status_strip.config(bg="#fffbeb", highlightbackground="#f59e0b")
            self.lbl_status_icon.config(text="🟡", bg="#fffbeb")
            self.lbl_status_head.config(text="STATUS: MICRO-MOTION DETECTED", fg="#b45309", bg="#fffbeb")
            self.lbl_status_desc.config(text="Subtle subcarrier phase deviation detected (human breathing or minor posture adjustment).", bg="#fffbeb")
        else:
            self.status_strip.config(bg=self.theme["ok_bg"], highlightbackground=self.theme["ok_border"])
            self.lbl_status_icon.config(text="🛡️", bg=self.theme["ok_bg"])
            self.lbl_status_head.config(text="ROOM SECURE — ZERO ANOMALIES", fg=self.theme["ok_text"], bg=self.theme["ok_bg"])
            self.lbl_status_desc.config(text="Fresnel reflection matrix is stationary. RF perturbation within ambient noise limit.", bg=self.theme["ok_bg"])

        # --------------------------------------------------------------------
        # 1. RENDER POLAR RADAR CANVAS
        # --------------------------------------------------------------------
        self.canvas_radar.delete("all")
        rw = self.canvas_radar.winfo_width() or 480
        rh = self.canvas_radar.winfo_height() or 270
        cx, cy = rw // 2, rh // 2
        max_r = min(cx, cy) - 15

        # Concentric distance rings
        ring_tags = ["1m", "2m", "3m", "4m", "5m"]
        for i, scale in enumerate([0.2, 0.4, 0.6, 0.8, 1.0]):
            cr = max_r * scale
            self.canvas_radar.create_oval(
                cx - cr, cy - cr, cx + cr, cy + cr,
                outline=self.theme["radar_grid"], width=1
            )
            # Distance labels
            self.canvas_radar.create_text(
                cx + cr - 10, cy - 6, text=ring_tags[i],
                font=("Consolas", 7), fill=self.theme["text_muted"]
            )

        # Crosshairs & Angle Rays (45 deg)
        self.canvas_radar.create_line(cx - max_r, cy, cx + max_r, cy, fill=self.theme["radar_grid"], dash=(2, 4))
        self.canvas_radar.create_line(cx, cy - max_r, cx, cy + max_r, fill=self.theme["radar_grid"], dash=(2, 4))

        # Node Icons (TX Beacon & RX Radar)
        tx_x, tx_y = cx - int(max_r * 0.7), cy
        rx_x, rx_y = cx + int(max_r * 0.7), cy
        self.canvas_radar.create_oval(tx_x - 6, tx_y - 6, tx_x + 6, tx_y + 6, fill="#f59e0b", outline="")
        self.canvas_radar.create_text(tx_x, tx_y - 12, text="TX BEACON", font=("Consolas", 7, "bold"), fill=self.theme["text_muted"])

        self.canvas_radar.create_oval(rx_x - 6, rx_y - 6, rx_x + 6, rx_y + 6, fill="#0284c7", outline="")
        self.canvas_radar.create_text(rx_x, rx_y - 12, text="RX RADAR", font=("Consolas", 7, "bold"), fill=self.theme["text_muted"])

        # Ellipsoidal Fresnel Reflection Zone outline
        self.canvas_radar.create_oval(
            cx - int(max_r * 0.8), cy - int(max_r * 0.45),
            cx + int(max_r * 0.8), cy + int(max_r * 0.45),
            outline=self.theme["text_accent"], width=1, dash=(3, 3)
        )

        # Echo Target Blips
        for b in list(self.blips):
            ang, radius, intensity = b
            bx = cx + math.cos(ang) * (max_r * radius)
            by = cy + math.sin(ang) * (max_r * radius)
            sz = 9 * intensity
            self.canvas_radar.create_oval(
                bx - sz, by - sz, bx + sz, by + sz,
                fill=self.theme["radar_blip"], outline=""
            )
            b[2] -= 0.04
            if b[2] <= 0:
                self.blips.remove(b)

        # Rotating Sweep Beam
        sx = cx + math.cos(self.sweep_angle) * max_r
        sy = cy + math.sin(self.sweep_angle) * max_r
        self.canvas_radar.create_line(cx, cy, sx, sy, fill=self.theme["radar_sweep"], width=2)
        self.sweep_angle = (self.sweep_angle + 0.05) % (math.pi * 2)

        # --------------------------------------------------------------------
        # 2. RENDER OFDM SUBCARRIER SPECTRUM CANVAS
        # --------------------------------------------------------------------
        self.canvas_spectrum.delete("all")
        sw = self.canvas_spectrum.winfo_width() or 480
        sh = self.canvas_spectrum.winfo_height() or 110

        bar_w = sw / self.num_subcarriers
        for k in range(self.num_subcarriers):
            # Dynamic simulated variance if demo or live
            if self.demo_mode or self.is_running:
                base_h = 10 + abs(math.sin(t * 3 + k * 0.3)) * (20 + (35 if self.is_alert else 0))
            else:
                base_h = 8

            bx0 = k * bar_w + 1
            bx1 = (k + 1) * bar_w - 1
            by0 = sh - min(sh - 10, base_h)
            by1 = sh - 4

            col = self.theme["radar_blip"] if (self.is_alert and k % 3 == 0) else self.theme["spectrum_bar"]
            self.canvas_spectrum.create_rectangle(bx0, by0, bx1, by1, fill=col, outline="")

        # --------------------------------------------------------------------
        # 3. RENDER OSCILLOSCOPE WAVEFORM CANVAS
        # --------------------------------------------------------------------
        self.canvas_wave.delete("all")
        ww = self.canvas_wave.winfo_width() or 500
        wh = self.canvas_wave.winfo_height() or 180

        # Horizontal grid guides
        for frac in [0.25, 0.5, 0.75]:
            gy = wh * frac
            self.canvas_wave.create_line(0, gy, ww, gy, fill=self.theme["wave_grid"], width=1)

        step_x = ww / (self.history_len - 1)
        max_val = max(35.0, max(self.threshold_history) * 1.6)

        def to_y(val):
            return wh - 10 - (min(max_val, val) / max_val) * (wh - 25)

        # Baseline Floor Line (gray dotted)
        pts_flr = []
        for i, val in enumerate(self.baseline_history):
            pts_flr.extend([i * step_x, to_y(val)])
        if len(pts_flr) >= 4:
            self.canvas_wave.create_line(*pts_flr, fill=self.theme["baseline_color"], width=1, dash=(2, 4))

        # Dynamic Threshold Line (dashed amber)
        pts_lim = []
        for i, val in enumerate(self.threshold_history):
            pts_lim.extend([i * step_x, to_y(val)])
        if len(pts_lim) >= 4:
            self.canvas_wave.create_line(*pts_lim, fill=self.theme["limit_color"], width=2, dash=(4, 2))

        # Motion Energy Waveform (cyan or red on alert)
        pts_mot = []
        for i, val in enumerate(self.motion_history):
            pts_mot.extend([i * step_x, to_y(val)])
        if len(pts_mot) >= 4:
            col = self.theme["alert_border"] if self.is_alert else self.theme["score_color"]
            self.canvas_wave.create_line(*pts_mot, fill=col, width=2)

        self.after(40, self._animate)


if __name__ == "__main__":
    app = RadarDesktopApp()
    app.mainloop()

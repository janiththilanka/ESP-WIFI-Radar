# 📡 Wi-Fi RF Motion Detection Radar (ESP32 + ESP8266) — v2.2

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-ESP32%20%7C%20ESP8266-red.svg)](https://www.espressif.com/)
[![Protocol](https://img.shields.io/badge/Protocol-ESP--NOW%20%7C%20802.11n%20CSI-orange.svg)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi.html#wi-fi-channel-state-information)
[![Display](https://img.shields.io/badge/Display-20x4%20I2C%20LCD-blueviolet.svg)](https://github.com/bperrybap/hd44780)
[![Console](https://img.shields.io/badge/GUI-WebSerial%20Cockpit%20(8%20Themes)-brightgreen.svg)](gui/index.html)
[![Hardware Verified](https://img.shields.io/badge/Hardware-Tested%20%26%20Verified-success.svg)](#-live-hardware-telemetry-gallery)

An **RF Multipath & CSI (Channel State Information) Wi-Fi Radar** built with **one ESP8266** and **one ESP32**, engineered according to state-of-the-art research from **Espressif esp-csi**, **ESPectre**, and **WaveSight**.

> **No optical sensors. No microphones. No cameras.**  
> This system transforms standard 2.4 GHz electromagnetic radio waves into an invisible volumetric perimeter radar. When a person moves between or near the nodes, their body alters multipath reflection patterns across OFDM subcarriers, enabling **through-wall intrusion detection**, **micro-motion monitoring**, and **standalone live telemetry**.

---

## 📸 Live Hardware Telemetry Gallery

The radar features a 100% standalone **20x4 I2C LCD Telemetry Display** running the auto-probing `hd44780` driver, delivering real-time room awareness without needing a computer or mobile phone.

<p align="center">
  <img src="docs/images/lcd_room_secure.jpg" width="48%" alt="Room Secure Status on 20x4 LCD" />
  <img src="docs/images/lcd_micro_motion.jpg" width="48%" alt="Micro-Motion Detected on 20x4 LCD" />
</p>

*Left: System in baseline state (`STATUS: ROOM SECURE`, Motion: 1.9, Limit: 10.0).*  
*Right: Human chest expansion / subtle movement detected (`STATUS: MICRO-MOTION`, Motion: 7.1, Limit: 11.5).*

---

## 🌟 Key Features & Advantages

### 🛡️ 1. Absolute Privacy Compliance (Zero Optical Surveillance)
- Cameras cannot be installed in private bedrooms, restrooms, patient quarters, or hotel suites due to legal and privacy concerns.
- RF CSI radar measures **electromagnetic field perturbations only**—it is physically impossible to spy on visual identity or capture imagery, protecting personal dignity while guaranteeing perimeter security.

### 🧱 2. Through-Wall & Non-Line-of-Sight (NLOS) Sensing
- 2.4 GHz radio waves naturally penetrate interior drywall, wooden doors, glass partitions, and plastic casings.
- Detects intruders walking in hallways or adjacent rooms before they enter the monitored perimeter.

### 🕵️ 3. Covert & Concealable Form Factor
- Because RF sensing requires no optical lens, the transmitter and receiver can be completely hidden inside standard electrical junction boxes, hollow drywall, ceiling cavities, books, or decorative household objects.
- An intruder cannot locate, cover, or blind the sensor with tape or spray paint.

### 📟 4. Standalone 20x4 I2C Hardware Telemetry
- Direct 4-wire connection to ESP32 hardware I2C pins (`GPIO 21 SDA`, `GPIO 22 SCL`).
- Real-time 4-line readout with automatic address resolution (`0x27` / `0x3F`), dynamic threshold tracking, link RSSI, and packet rate.

### 💻 5. Next-Gen WebSerial Tactical Console (`gui/index.html`)
- Zero installation: Runs natively in Google Chrome, Edge, Brave, and Opera via the HTML5 WebSerial API.
- **8 Curated Themes**: Yellow VMS, Nordic Slate, Swiss Clean, Tactical Dark, Cyber Emerald, Deep Space, Solar Amber, and Cyberpunk Neon.
- **Interactive Visualizers**: 52-channel OFDM waterfall heatmap, live disturbance oscilloscope, and subcarrier jitter spectrum analyzer.
- **Precision DSP Calibrator**: Live tactile tuning of sensitivity multipliers, noise offset margin, pre-amp gain, debounce frames, and 4 quick-preset profiles.

---

## 🔬 Scientific Principles & DSP Architecture

For full mathematical derivations and academic citations, see [**`docs/RESEARCH_AND_FINETUNING.md`**](docs/RESEARCH_AND_FINETUNING.md).

```
+---------------------+            Fresnel Reflection Zone            +---------------------+
|   ESP8266 Node      |   ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ >   |     ESP32 Node      |
|  (Transmitter TX)   |             \            🚶 (Human Motion)     |   (CSI Engine RX)   |
| 33 Hz ESP-NOW Pulse |   ~ ~ ~ ~ ~  \ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ >  | 25 Hz DSP Pipeline  |
+---------------------+               Perturbed Subcarrier Multipath  +----------+----------+
                                                                                 |
                                          +--------------------------------------+--------------------------------------+
                                          |                                                                             |
                                  [20x4 I2C LCD Display]                                                    [WebSerial GUI Dashboard]
                                  - Live Room Status                                                        - 8 Curated UI Themes
                                  - Motion Score vs Limit                                                   - OFDM Subcarrier Waterfall
                                  - Beacon Link & RSSI                                                      - Live Oscilloscope Waveform
                                  - Packet Rate & Baseline                                                  - Real-time DSP Calibrator
```

### 1. The Fresnel Zone Phenomenon
When the ESP8266 transmits 802.11n pulses to the ESP32, radio waves travel along direct and indirect paths, forming concentric ellipsoidal **Fresnel Zones**:

$$r_n = \sqrt{\frac{n \lambda d_1 d_2}{d_1 + d_2}}$$

Because human tissue is composed of >60% water, an individual entering or moving within the Fresnel zone reflects, refracts, and scatters RF waves, inducing rapid frequency-selective constructive and destructive interference.

### 2. CSI (Channel State Information) vs. RSSI
- **RSSI** is a single coarse scalar value representing total received power; it fails to differentiate between a person moving and normal atmospheric attenuation.
- **CSI** provides a complex matrix of transfer functions across **52 distinct OFDM subcarriers**:

$$H(k) = \|H(k)\| e^{j \angle H(k)} = I(k) + j Q(k)$$

By tracking per-subcarrier phase and amplitude deviations, the ESP32 detects microscopic disturbances (such as human respiration or hand gestures) that leave total RSSI completely unchanged.

### 3. Four-Stage Microcontroller DSP Pipeline

```
Raw 802.11n CSI Packet
         │
         ▼
[ Stage 1: AGC-Invariant Normalization ]  --> Cancels receiver amplifier gain stepping
         │
         ▼
[ Stage 2: Hampel Outlier Filter ]        --> Sliding window MAD eliminates transient RF spikes
         │
         ▼
[ Stage 3: Statistical Rolling Metrics ]  --> Computes mean, standard deviation & motion energy
         │
         ▼
[ Stage 4: Asymmetric Dual-Rate Baseline] --> Freezes baseline during motion; auto-adapts when calm
         │
         ├──> Output: 20x4 I2C Hardware LCD
         ├──> Output: GPIO 2 Status LED / Buzzer
         └──> Output: WebSerial Telemetry Stream (115200 Baud)
```

1. **AGC (Automatic Gain Control) Invariant Normalization**:
   $$\hat{A}_k = \frac{A_k}{\frac{1}{K}\sum_{j=0}^{K-1} A_j}$$
   Normalizes subcarrier amplitudes against the instantaneous frame mean, completely eliminating false alarms caused by ESP32 internal hardware amplifier gain switches.
2. **Hampel Outlier Rejection**:
   Uses a 5-frame sliding window with Median Absolute Deviation (MAD) to filter out transient impulse noise from neighboring Bluetooth, microwave ovens, and Wi-Fi routers.
3. **Statistical Feature Extraction**:
   A 25-sample rolling history buffer computes real-time standard deviation and mean perturbation at 25 Hz.
4. **Asymmetric Dual-Rate Adaptive Baseline**:
   - **Calm Room**: Noise floor baseline smoothly tracks ambient temperature and drift ($\alpha = 0.008$).
   - **Active Intrusion**: Baseline updates **immediately freeze**, preventing an intruder's presence from contaminating the baseline and turning off the alarm prematurely.

---

## 🛠️ Hardware Requirements & Bill of Materials

| Component | Quantity | Purpose | Approximate Cost |
| :--- | :---: | :--- | :---: |
| **ESP32 DevKit V1** (or ESP-WROOM-32) | 1 | CSI Demodulation, DSP Pipeline, LCD & Serial Driver | ~$3.50 |
| **ESP8266 NodeMCU** (or Wemos D1 Mini / ESP-01) | 1 | Dedicated 33 Hz ESP-NOW RF Pulse Transmitter | ~$2.00 |
| **20x4 Character LCD + I2C Backpack (PCF8574)** | 1 | Standalone physical telemetry display | ~$4.00 |
| **Female-to-Female Jumper Wires** | 4 | Wiring LCD to ESP32 I2C pins | ~$0.50 |
| **Micro-USB / USB-C Cables** | 2 | Power & firmware flashing | Existing |
| **Optional: 5V Piezo Buzzer / External LED** | 1 | Connected to ESP32 **GPIO 2** for audible alarm | ~$0.50 |

---

## 🔌 Complete Wiring Diagram

### 1. ESP32 Receiver & 20x4 I2C LCD Connections

```
     ESP32 DevKit V1                        20x4 I2C LCD Backpack
   +-----------------+                       +-----------------+
   |                 |                       |                 |
   |         VIN(5V) |======================>| VCC             | (Requires 5V for optical contrast)
   |             GND |======================>| GND             |
   |   GPIO 21 (G21) |======================>| SDA             | (I2C Serial Data)
   |   GPIO 22 (G22) |======================>| SCL             | (I2C Serial Clock)
   |                 |                       |                 |
   |    GPIO 2 (LED) |----[ Optional Buzzer/LED ]             | [Blue Contrast Trimmer]
   |                 |                       | [LED Jumper Cap] |
   +-----------------+                       +-----------------+
```

| LCD Pin | ESP32 Pin | Logic Level | Connection Notes |
| :--- | :--- | :--- | :--- |
| **`VCC`** | **`VIN` (5V)** | 5.0 V DC | **CRITICAL**: Must connect to `VIN` (5V from USB). Connecting to `3V3` will make characters faint or invisible. |
| **`GND`** | **`GND`** | 0 V | Common ground reference. |
| **`SDA`** | **`GPIO 21` (`G21`)**| 3.3 V / 5 V | Hardware I2C Serial Data. |
| **`SCL`** | **`GPIO 22` (`G22`)**| 3.3 V / 5 V | Hardware I2C Serial Clock (100 kHz standard clock). |

> **💡 Hardware Checklist:**
> 1. **Contrast Trimmer:** If the LCD turns on but letters are faint or solid rectangles, gently turn the small brass screw on the blue potentiometer on the back of the LCD with a screwdriver until characters appear crisp.
> 2. **Backlight Jumper:** Ensure the small black 2-pin jumper cap labeled **`LED`** on the backpack is firmly in place.
> 3. **Auto-Detection:** The firmware uses Bill Perry's `hd44780` library, which automatically identifies both `0x27` and `0x3F` I2C addresses and auto-probes the pinout mapping.

### 2. ESP8266 Transmitter
- **No external wiring required!** Simply plug the ESP8266 into any USB wall charger, 5V power bank, or phone adapter in the room being monitored.

---

## 📟 20x4 LCD Telemetry Interface

The screen is formatted into four 20-character telemetry rows:

```text
+--------------------+
|STATUS: ROOM SECURE |  <-- Row 0: Real-time System Alert State
|MOT:  1.9  LIM: 10.0|  <-- Row 1: Instantaneous Motion vs Dynamic Threshold
|BCN: ONLINE  -60 dBm|  <-- Row 2: Transmitter Link Status & RSSI
|RATE: 34PPS  FLR:2.5|  <-- Row 3: Transmission Packet Rate & Noise Floor
+--------------------+
```

| Row | Label | Description | Example Values |
| :---: | :--- | :--- | :--- |
| **0** | **System State** | High-level room awareness status. | `STATUS: ROOM SECURE` (Calm)<br>`STATUS: MICRO-MOTION` (Subtle)<br>`! INTRUSION ALERT !` (Active motion)<br>`STATUS: BCN OFFLINE ` (Signal lost) |
| **1** | **`MOT` / `LIM`** | Live filtered motion score vs. dynamic release threshold limit. | `MOT:  1.9  LIM: 10.0` (Quiet)<br>`MOT: 14.5  LIM: 10.0` (Triggered) |
| **2** | **`BCN` / RSSI** | Transmitter connectivity and physical received signal strength. | `BCN: ONLINE  -60 dBm`<br>`BCN: SEARCHING...   ` |
| **3** | **`RATE` / `FLR`**| CSI packet arrival rate per second and ambient noise floor. | `RATE: 34PPS  FLR: 2.5` |

---

## 💻 Dual Interface Options

### Option A: Next-Gen WebSerial GUI Console (Recommended)

Open [`gui/index.html`](gui/index.html) directly in any Chromium-based browser (Chrome, Edge, Brave, Opera) and click **⚡ Connect ESP32**.

<p align="center">
  <kbd><img src="docs/images/lcd_room_secure.jpg" width="80%" alt="Radar Console" /></kbd>
</p>

- **8 Curated Aesthetic Themes:**
  - ☀️ **Yellow VMS** (Scandinavian high-contrast security architecture)
  - ❄️ **Nordic Slate** (Cool steel telemetry console)
  - 🏢 **Swiss Clean** (Minimalist laboratory monochrome with signal red calipers)
  - 🌙 **Tactical Dark** (Stealth obsidian void with neon cyan phosphor)
  - ⚡ **Cyber Emerald** (CRT military radar phosphor matrix)
  - 🌌 **Deep Space** (NASA/SpaceX aerospace telemetry)
  - 🌅 **Solar Amber** (Industrial hazard and safety console)
  - 🌆 **Cyberpunk Neon** (Retrowave sunset synthwave)
- **Fullscreen Cockpit Mode (`⛶`):** One-click toggle for full-screen landscape operation.
- **Real-Time Visualizers:**
  - 20 MHz 802.11n Wi-Fi OFDM Subcarrier Waterfall Heatmap.
  - Live Oscilloscope Waveform tracking disturbance energy against adaptive threshold and baseline noise floor.
  - 52-Channel Subcarrier Jitter Spectrum Analyzer.
- **High-Contrast Precision DSP Calibrator:**
  - Sliders for Sensitivity Factor (`1.0x` – `12.0x`), Noise Margin Offset (`0.5` – `30.0`), Pre-Amp Gain (`0.2x` – `5.0x`), Manual Override, Trigger Debounce (`1` – `8` frames), and Hold Duration (`200` – `15,000 ms`).
  - 4 Quick-Preset Profiles: **🫁 Micro-Presence**, **👤 Balanced**, **🏃 Walking Alarm**, and **🐾 Pet-Immunity**.
  - One-click **5-Second Empty Room Auto-Calibration**.
- **Sonar Audio & Security Log:** Synthesized audio alarm with mute switch and real-time security event log with CSV export.

### Option B: Standalone Python Desktop GUI

For headless or offline environments:
```bash
pip install pyserial
python gui/radar_desktop.py
```

---

## 🚀 Quick Setup & Installation Guide

### Step 1: Arduino IDE Configuration
1. Open **Arduino IDE**.
2. Go to **File -> Preferences** and add the following URLs to **Additional Boards Manager URLs**:
   ```text
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   http://arduino.esp8266.com/stable/package_esp8266com_index.json
   ```
3. Go to **Tools -> Board -> Boards Manager...**:
   - Search for **esp32** by *Espressif Systems* and click **Install**.
   - Search for **esp8266** by *ESP8266 Community* and click **Install**.
4. Go to **Sketch -> Include Library -> Manage Libraries...**:
   - Search for **`hd44780`** by *Bill Perry* and click **Install**.

---

### Step 2: Flash the ESP8266 Transmitter Beacon
1. Connect the **ESP8266** to your computer via USB.
2. Open [`esp8266_tx_beacon/esp8266_tx_beacon.ino`](esp8266_tx_beacon/esp8266_tx_beacon.ino).
3. Under **Tools**:
   - **Board**: Select your ESP8266 board (e.g. *NodeMCU 1.0 (ESP-12E Module)* or *LOLIN(WEMOS) D1 R2 & mini*).
   - **Port**: Select the COM port for the ESP8266.
4. Click **Upload**.
5. Once uploaded, the onboard LED will blink periodically (~33 pulses/sec). Disconnect it and place it anywhere in the room powered by a USB charger.

---

### Step 3: Flash the ESP32 Receiver & Radar Engine
1. Connect the **ESP32** to your computer via USB.
2. Open [`esp32_radar_rx/esp32_radar_rx.ino`](esp32_radar_rx/esp32_radar_rx.ino).
3. Under **Tools**:
   - **Board**: Select *ESP32 Dev Module*.
   - **Port**: Select the COM port for the ESP32.
4. Click **Upload**.
5. Open **Tools -> Serial Monitor** at **115200 baud**. You will see:
   ```text
   =========================================================
    ESP32 Wi-Fi Motion Radar (v2.2 Full Precision DSP)
   =========================================================
   [OK] CSI Engine initialized.
   [LCD] hd44780 20x4 LCD detected & initialized successfully!
   [STATUS] Radar active. Ready for Web Dashboard.
   ```
6. The 20x4 LCD backlight will flash twice, display the boot sequence, and enter live telemetry mode!

---

## 🎯 Physical Placement & Environmental Tuning

| Parameter | Recommended Setting | Rationale |
| :--- | :--- | :--- |
| **Inter-Node Distance** | 2 to 6 meters | Establishes an expansive Fresnel reflection zone across the room. |
| **Elevation** | 1.0 to 1.5 meters from floor | Matches human torso height for maximum cross-sectional RF scattering. |
| **Through-Wall Sensing** | Place ESP8266 in hallway, ESP32 inside room | 2.4 GHz signals pass through doors and drywall, detecting approaching motion. |
| **Sensitivity Factor** | `2.2f` (Balanced default) | Lower (`1.8f`) for subtle presence; Higher (`3.0f`) to filter out pets. |
| **Trigger Debounce** | `2` to `3` consecutive frames | Requires sustained perturbation, rejecting random RF spikes. |
| **Hold Time** | `1500 ms` | Keeps alarm asserted continuously between natural human footsteps. |

---

## ⚠️ Limitations & Accuracy Considerations

1. **Non-Line-of-Sight Scattering:**
   Because 2.4 GHz radio waves reflect off walls and furniture, large metallic objects (such as rotating metal ceiling fans) can induce periodic subcarrier perturbations if placed directly between the nodes.
   *Mitigation:* Use the WebSerial calibrator to raise the `minThresholdOffset` margin or switch to the **Pet-Immune** preset.
2. **Multi-Target Resolution:**
   A single transmitter-receiver pair operates as a volumetric presence and activity sensor; it detects *that* motion occurred and *how intensely*, but cannot resolve exact $(x, y, z)$ spatial coordinates without additional receiver nodes.
3. **RF Congestion on Channel 1:**
   In extremely crowded 2.4 GHz environments with dozens of active routers, packet loss may occur. Both nodes can be switched to Channel 6 or 11 by changing `RADAR_WIFI_CHANNEL` in both sketches.

---

## 🔮 Future Roadmap & Upgrades

- [ ] **Multi-Static Mesh Localization**: Deploying 3 or more ESP32 nodes to triangulate exact $(x, y)$ human coordinates via multi-angle intersection.
- [ ] **Native Home Wi-Fi Router Integration**: Capturing CSI passively from existing home Wi-Fi traffic without needing a dedicated ESP8266 transmitter beacon.
- [ ] **TinyML Respiration & Fall Detection**: Running lightweight 1D-CNN or LSTM neural networks on the ESP32 to differentiate between walking, sitting, breathing, and medical fall emergencies.

---

## 📚 Academic Citations & Acknowledgments

This project builds upon pioneering academic research and open-source contributions in Wi-Fi sensing:
- **[Espressif esp-csi](https://github.com/espressif/esp-csi)** — Official ESP32 Channel State Information framework.
- **[ESPectre](https://github.com/francescopace/ESPectre)** (Francesco Pace) — Microcontroller-optimized mathematical signal processing for Wi-Fi sensing.
- **[WaveSight](https://github.com/ErfanDL/WaveSight)** (ErfanDL) — Real-time CSI web visualization and calibration workflows.
- **[ESP32-CSI-Tool](https://stevenmhernandez.github.io/ESP32-CSI-Tool/)** (Steven M. Hernandez & E. Bulut) — Foundational academic CSI extraction framework.
- **[hd44780](https://github.com/bperrybap/hd44780)** (Bill Perry) — Auto-probing, high-speed cross-platform LCD driver library.

---

## 📄 License

This project is licensed under the **MIT License** — feel free to modify, deploy, and build upon it for personal, academic, or commercial applications.

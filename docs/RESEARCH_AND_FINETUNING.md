# 🔬 Wi-Fi CSI Motion Detection Radar: Comprehensive Research & Engineering Analysis

This document synthesizes findings from leading academic research, official Espressif documentation, and state-of-the-art open-source projects for human motion sensing using Wi-Fi Channel State Information (CSI) on ESP32 microcontrollers.

---

## 1. Key Projects & Literature Reviewed

### A. Official Espressif Frameworks
- **[espressif/esp-csi](https://github.com/espressif/esp-csi)**:
  - Official framework providing `esp_wifi_set_csi_rx_cb()`, `esp_wifi_sensing`, `esp-radar`, and `esp-csi-gain-ctrl`.
  - Introduces finite-state machine (FSM) models for presence detection and dynamic baseline tracking.
  - Highlights the role of **Automatic Gain Control (AGC)**: Hardware gain changes in the ESP32 receiver create step-discontinuities in raw amplitude that mimic motion unless compensated.

### B. Benchmark Community & Open-Source Projects
- **[ESPectre](https://github.com/francescopace/ESPectre) (by Francesco Pace)**:
  - High-performance, lightweight mathematical signal processing engine for ESP32.
  - Uses **MVS (Motion Vector Sensing)**, **Hampel outlier filtering**, and a 11.0 Hz low-pass filter to isolate human body Doppler shifts.
  - Replaces heavy machine learning with variance and statistical segment thresholds, enabling ultra-fast real-time inference on microcontroller cores.
- **[WaveSight](https://github.com/ErfanDL/WaveSight) (by ErfanDL)**:
  - ESP32 Wi-Fi CSI radar with real-time web dashboard for live RSSI and CSI jitter visualization.
  - Implements a dedicated auto-calibration cycle (recording 30–60 seconds of empty-room ambient RF noise) to establish an optimal noise floor.
- **[ESP32-CSI-Tool](https://stevenmhernandez.github.io/ESP32-CSI-Tool/) (by Steven M. Hernandez & E. Bulut)**:
  - Groundbreaking academic toolkit demonstrating raw CSI capture on ESP32 across 802.11n subcarriers.
  - Proves that 802.11n OFDM subcarriers (52/56 data subcarriers) provide spatial multipath resolution capable of detecting breathing and through-wall movement.

---

## 2. Core Scientific Principles

### 2.1 The Fresnel Zone & Multipath Scattering
When an RF signal travels from the transmitter (ESP8266) to the receiver (ESP32), it propagates not only along the direct Line-of-Sight (LoS) path, but also bounces off the floor, ceiling, walls, and objects, forming concentric ellipsoidal zones known as **Fresnel Zones**:

$$r_n = \sqrt{\frac{n \lambda d_1 d_2}{d_1 + d_2}}$$

Where:
- $\lambda \approx 12.5\text{ cm}$ for $2.4\text{ GHz}$ Wi-Fi
- $d_1, d_2$ are distances from the transmitter and receiver to the moving target
- $n = 1$ is the first Fresnel zone (contains ~70% of transmitted RF energy)

When a human body enters or moves through the Fresnel zone, its high water content (>60%) absorbs, reflects, and diffracts the RF waves. This creates constructive and destructive phase interference patterns across individual subcarrier frequencies.

### 2.2 Channel State Information (CSI) vs. RSSI
- **RSSI (Received Signal Strength Indicator)**: A single macroscopic scalar representing total received energy. Prone to severe temporal fading, multipath cancellation, and coarse sensitivity.
- **CSI (Channel State Information)**: A matrix of complex transfer coefficients representing amplitude and phase response for every individual subcarrier channel $k$:

$$H(k) = \|H(k)\| e^{j \angle H(k)} = I(k) + j Q(k)$$

In 20 MHz Wi-Fi (HT20), there are 64 subcarriers spaced at 312.5 kHz. CSI captures fine-grained, frequency-selective fading that makes microscopic motions (such as chest expansion or slow steps) detectable even when RSSI does not shift.

---

## 3. Critical Engineering Challenges & Solutions

### 3.1 Challenge 1: Receiver AGC (Automatic Gain Control) Drift
- **Problem**: The ESP32 hardware radio contains an internal AGC that dynamically adjusts Low Noise Amplifier (LNA) and Variable Gain Amplifier (VGA) attenuation. If packet signal level varies, the AGC switches gain tiers, causing abrupt jumps across all subcarriers simultaneously.
- **Solution — Amplitude Vector Normalization**:
  Instead of raw subcarrier amplitudes $A_k = \sqrt{I_k^2 + Q_k^2}$, compute the instantaneous frame mean:
  $$\mu_A = \frac{1}{K} \sum_{k=0}^{K-1} A_k$$
  And normalize every subcarrier:
  $$\hat{A}_k = \frac{A_k}{\mu_A}$$
  When an AGC step occurs, all subcarriers scale uniformly, so $\hat{A}_k$ remains constant. Only non-uniform multipath changes (caused by human movement) alter the normalized vector shape.

### 3.2 Challenge 2: Single-Frame Glitches & RF Spikes
- **Problem**: Neighboring 2.4 GHz traffic, Bluetooth hopping, and microwave oven harmonics cause transient single-packet outliers.
- **Solution — Hampel Filter**:
  A sliding window of 5 frames tracks the median $\tilde{x}$ and Median Absolute Deviation (MAD):
  $$\text{MAD} = \text{median}(|x_i - \tilde{x}|)$$
  If $|x - \tilde{x}| > 3.0 \times 1.4826 \times \text{MAD}$, the value is identified as an impulse outlier and replaced by $\tilde{x}$.

### 3.3 Challenge 3: Baseline Contamination during Motion
- **Problem**: If the baseline noise floor continuously adapts while a person is moving, the baseline will rise to meet the motion score, causing the alert to turn off prematurely while the person is still in the room.
- **Solution — Asymmetric Dual-Rate Adaptive Baseline**:
  - When **No Motion** is detected: Baseline slowly adapts ($\alpha = 0.015$) to ambient thermal noise.
  - When **Motion** is detected: Baseline updates are **frozen**, preventing baseline contamination.
  - **Hysteresis**: Upper threshold $T_{high} = \text{Baseline} \times S$, Lower threshold $T_{low} = T_{high} \times 0.75$.

### 3.4 Challenge 4: Multi-Device Interference
- **Problem**: In a typical home or office, hundreds of packets per second arrive from neighboring Wi-Fi routers, phones, and smart TVs on Channel 1.
- **Solution — Transmitter MAC Pinning**:
  The ESP32 receiver validates the transmitter's MAC address (`84:cc:a8:81:e1:bb`) and payload signature (`"WIFI_RAD"`). Non-matching packets are discarded before CSI processing.

---

## 4. Fine-Tuning Parameter Matrix

| Parameter | Default | Recommended Range | Impact |
| :--- | :--- | :--- | :--- |
| **`SENSITIVITY_FACTOR`** | `2.2` | `1.6 – 3.2` | Multiplier above baseline noise. `1.8` for subtle movement/breathing; `2.8` for human-only walking (ignoring pets). |
| **`MIN_THRESHOLD_OFFSET`**| `8.0` | `5.0 – 14.0` | Minimum noise margin. Prevents triggers in ultra-quiet RF environments. |
| **`TRIGGER_COUNT`** | `3` frames | `2 – 5` frames | Number of consecutive frames exceeding threshold before triggering alert. Eliminates single-packet spikes. |
| **`HOLD_TIME_MS`** | `1500 ms` | `1000 – 4000 ms`| Time in ms the alert state remains high after motion stops. |
| **`PULSE_RATE`** | `33 Hz` (30ms) | `25 – 50 Hz` | Transmitter pulse frequency. Higher rate = better Doppler resolution; 33 Hz is optimal for low airtime congestion. |

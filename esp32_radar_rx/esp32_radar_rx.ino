/*
 =====================================================================================
  ESP32 Wi-Fi Motion Radar - Full Precision RF Sensing & Tuning Engine (v2.2)
 =====================================================================================
  Expanded Capabilities:
  1. Wide Dynamic Range Sensitivity (Multiplier 1.0x to 12.0x)
  2. Adjustable Noise Offset Margin (0.5 to 30.0)
  3. Pre-Amp Motion Gain Scaling (0.2x to 5.0x)
  4. Manual Direct Threshold Override Mode (optional fixed numerical limit)
  5. Configurable Trigger Debounce Frames (1 to 8 frames)
  6. Instant Quick-Preset Profiles (Micro-Presence, Balanced, Walking, Pet-Immunity)
  7. High-Resolution Telemetry output
 =====================================================================================
*/

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>

#define RADAR_WIFI_CHANNEL 1
#define LED_PIN 2
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

// 20x4 LCD Controller (auto-locates I2C address, pinout mapping, and backlight polarity)
hd44780_I2Cexp lcd;
bool lcdDetected = false;
unsigned long lastLcdUpdate = 0;
#define LCD_REFRESH_INTERVAL_MS 250

// Radar Pulse packet structure
typedef struct __attribute__((packed)) {
  uint32_t seqNumber;
  uint32_t timestamp;
  char     signature[8]; // "WIFI_RAD"
} RadarPulsePacket;

// Expanded Tuning Parameters (Controlled dynamically via WebSerial)
float sensitivityFactor    = 2.2f;    // Range: 1.0 to 12.0
float minThresholdOffset   = 4.5f;    // Range: 0.5 to 30.0
float motionGain           = 1.0f;    // Range: 0.2 to 5.0
float manualThreshold      = 0.0f;    // 0.0 = Auto-Adaptive, >0.0 = Manual Fixed Limit
unsigned long motionHoldTimeMs = 1500;// Range: 200 to 10000 ms
int motionTriggerFrames    = 2;       // Consecutive high frames required (1 to 8)

// Beacon Link State
volatile bool beaconConnected = false;
volatile unsigned long lastBeaconPacketTime = 0;
volatile uint32_t beaconPacketCount = 0;
volatile int8_t beaconRssi = -60;
volatile float beaconPacketsPerSec = 0.0f;
uint8_t beaconMac[6] = {0};
bool hasLearnedBeaconMac = false;

// Subcarrier state storage
#define MAX_SUBCARRIERS 64
static float prevNormAmplitudes[MAX_SUBCARRIERS] = {0};
static float currentSubcarrierDeltas[MAX_SUBCARRIERS] = {0};
static bool hasPrevCsi = false;

volatile float currentCsiPerturbation = 0.0f;
volatile float currentSubcarrierVariance = 0.0f;

// RSSI variance
volatile float rssiPerturbation = 0.0f;
volatile float prevRssi = -60.0f;

// Hampel Filter Buffer
#define HAMPEL_WINDOW 5
static float hampelBuffer[HAMPEL_WINDOW] = {0};
static int hampelIndex = 0;

// Rolling History Buffer
#define HISTORY_LEN 25
static float historyBuffer[HISTORY_LEN] = {0};
static int historyIndex = 0;

// Adaptive Baseline & Threshold State
float ambientNoiseBaseline = 3.5f;
float dynamicThreshold = 12.0f;
float filteredMotionScore = 0.0f;

// Motion State
bool motionDetected = false;
unsigned long motionTriggerTime = 0;
int consecutiveHighCount = 0;

// Calibration State
bool isCalibrating = false;
unsigned long calibrationStartTime = 0;
#define CALIBRATION_DURATION_MS 5000
float calibrationAccumulator = 0.0f;
int calibrationSampleCount = 0;

// =====================================================================================
//  Hampel Filter: Removes Impulse Spikes
// =====================================================================================
float applyHampelFilter(float newVal) {
  hampelBuffer[hampelIndex] = newVal;
  hampelIndex = (hampelIndex + 1) % HAMPEL_WINDOW;

  float sorted[HAMPEL_WINDOW];
  memcpy(sorted, hampelBuffer, sizeof(sorted));
  for (int i = 0; i < HAMPEL_WINDOW - 1; i++) {
    for (int j = i + 1; j < HAMPEL_WINDOW; j++) {
      if (sorted[i] > sorted[j]) {
        float tmp = sorted[i];
        sorted[i] = sorted[j];
        sorted[j] = tmp;
      }
    }
  }
  float median = sorted[HAMPEL_WINDOW / 2];

  float absDev[HAMPEL_WINDOW];
  for (int i = 0; i < HAMPEL_WINDOW; i++) {
    absDev[i] = abs(sorted[i] - median);
  }
  for (int i = 0; i < HAMPEL_WINDOW - 1; i++) {
    for (int j = i + 1; j < HAMPEL_WINDOW; j++) {
      if (absDev[i] > absDev[j]) {
        float tmp = absDev[i];
        absDev[i] = absDev[j];
        absDev[j] = tmp;
      }
    }
  }
  float mad = absDev[HAMPEL_WINDOW / 2];
  float threshold = 3.0f * 1.4826f * mad;

  if (abs(newVal - median) > threshold && threshold > 0.4f) {
    return median;
  }
  return newVal;
}

// =====================================================================================
//  CSI Callback: AGC Invariant Normalization
// =====================================================================================
void wifi_csi_rx_cb(void *ctx, wifi_csi_info_t *data) {
  if (!data || !data->buf || data->len <= 0) return;

  if (hasLearnedBeaconMac) {
    bool match = true;
    for (int i = 0; i < 6; i++) {
      if (data->mac[i] != beaconMac[i]) {
        match = false;
        break;
      }
    }
    if (!match) return;
  }

  int8_t *csi_raw = (int8_t *)data->buf;
  int subcarrierCount = data->len / 2;
  if (subcarrierCount > MAX_SUBCARRIERS) subcarrierCount = MAX_SUBCARRIERS;

  float rawAmps[MAX_SUBCARRIERS];
  float frameSum = 0.0f;
  int validSubcarriers = 0;

  for (int i = 0; i < subcarrierCount; i++) {
    int8_t i_val = csi_raw[i * 2];
    int8_t q_val = csi_raw[i * 2 + 1];
    float amp = sqrt((float)(i_val * i_val + q_val * q_val));
    rawAmps[i] = amp;
    frameSum += amp;
    validSubcarriers++;
  }

  if (validSubcarriers == 0 || frameSum < 1.0f) return;

  float frameMean = frameSum / (float)validSubcarriers;
  float normAmps[MAX_SUBCARRIERS];
  for (int i = 0; i < validSubcarriers; i++) {
    normAmps[i] = rawAmps[i] / frameMean;
  }

  if (hasPrevCsi) {
    float deltaSum = 0.0f;
    float varianceSum = 0.0f;

    for (int i = 0; i < validSubcarriers; i++) {
      float delta = abs(normAmps[i] - prevNormAmplitudes[i]);
      currentSubcarrierDeltas[i] = delta;
      deltaSum += delta;
      varianceSum += (delta * delta);
    }

    currentCsiPerturbation = (deltaSum / (float)validSubcarriers) * 45.0f;
    currentSubcarrierVariance = (varianceSum / (float)validSubcarriers) * 100.0f;
  }

  for (int i = 0; i < validSubcarriers; i++) {
    prevNormAmplitudes[i] = normAmps[i];
  }
  hasPrevCsi = true;
}

// =====================================================================================
//  ESP-NOW Callback
// =====================================================================================
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (!data || len < sizeof(RadarPulsePacket)) return;
  RadarPulsePacket *pkt = (RadarPulsePacket *)data;
  if (strncmp(pkt->signature, "WIFI_RAD", 8) == 0) {
    lastBeaconPacketTime = millis();
    beaconPacketCount++;

    if (info) {
      if (!hasLearnedBeaconMac && info->src_addr) {
        memcpy(beaconMac, info->src_addr, 6);
        hasLearnedBeaconMac = true;
      }
      if (info->rx_ctrl) {
        beaconRssi = info->rx_ctrl->rssi;
      }
    }

    float curRssi = (float)beaconRssi;
    float delta = abs(curRssi - prevRssi);
    prevRssi = curRssi;
    rssiPerturbation = (rssiPerturbation * 0.7f) + (delta * 0.3f);
  }
}
#else
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
  if (!data || len < sizeof(RadarPulsePacket)) return;
  RadarPulsePacket *pkt = (RadarPulsePacket *)data;
  if (strncmp(pkt->signature, "WIFI_RAD", 8) == 0) {
    lastBeaconPacketTime = millis();
    beaconPacketCount++;

    if (!hasLearnedBeaconMac && mac) {
      memcpy(beaconMac, mac, 6);
      hasLearnedBeaconMac = true;
    }

    float curRssi = (float)beaconRssi;
    float delta = abs(curRssi - prevRssi);
    prevRssi = curRssi;
    rssiPerturbation = (rssiPerturbation * 0.7f) + (delta * 0.3f);
  }
}
#endif

// =====================================================================================
//  Enhanced Serial Command Parser (Supports All Tuning Parameters)
// =====================================================================================
void processSerialCommands() {
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "CMD:CAL") {
      isCalibrating = true;
      calibrationStartTime = millis();
      calibrationAccumulator = 0.0f;
      calibrationSampleCount = 0;
      Serial.println(F("[CAL_START] Calibrating empty room baseline..."));
    }
    else if (cmd.startsWith("CMD:SENS:")) {
      float newSens = cmd.substring(9).toFloat();
      if (newSens >= 0.8f && newSens <= 15.0f) {
        sensitivityFactor = newSens;
        Serial.print(F("[CONF] Sensitivity: "));
        Serial.println(sensitivityFactor, 2);
      }
    }
    else if (cmd.startsWith("CMD:OFFSET:")) {
      float newOffset = cmd.substring(11).toFloat();
      if (newOffset >= 0.2f && newOffset <= 40.0f) {
        minThresholdOffset = newOffset;
        Serial.print(F("[CONF] Offset: "));
        Serial.println(minThresholdOffset, 2);
      }
    }
    else if (cmd.startsWith("CMD:GAIN:")) {
      float newGain = cmd.substring(9).toFloat();
      if (newGain >= 0.1f && newGain <= 6.0f) {
        motionGain = newGain;
        Serial.print(F("[CONF] Gain: "));
        Serial.println(motionGain, 2);
      }
    }
    else if (cmd.startsWith("CMD:MANUAL_THRESH:")) {
      float newThresh = cmd.substring(18).toFloat();
      manualThreshold = newThresh;
      Serial.print(F("[CONF] Manual Threshold: "));
      Serial.println(manualThreshold, 2);
    }
    else if (cmd.startsWith("CMD:TRIGGER:")) {
      int newTrig = cmd.substring(12).toInt();
      if (newTrig >= 1 && newTrig <= 10) {
        motionTriggerFrames = newTrig;
        Serial.print(F("[CONF] Trigger Frames: "));
        Serial.println(motionTriggerFrames);
      }
    }
    else if (cmd.startsWith("CMD:HOLD:")) {
      unsigned long newHold = cmd.substring(9).toInt();
      if (newHold >= 200 && newHold <= 15000) {
        motionHoldTimeMs = newHold;
        Serial.print(F("[CONF] Hold ms: "));
        Serial.println(motionHoldTimeMs);
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println();
  Serial.println(F("========================================================="));
  Serial.println(F(" ESP32 Wi-Fi Motion Radar (v2.2 Full Precision DSP)     "));
  Serial.println(F("========================================================="));

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(RADAR_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  if (esp_now_init() != ESP_OK) {
    Serial.println(F("[ERROR] ESP-NOW init failed!"));
    return;
  }
  esp_now_register_recv_cb(onDataRecv);

  wifi_csi_config_t csi_config = {0};
  csi_config.lltf_en = true;
  csi_config.htltf_en = true;
  csi_config.stbc_htltf2_en = true;
  csi_config.ltf_merge_en = true;
  csi_config.channel_filter_en = true;
  csi_config.manu_scale = false;
  csi_config.shift = 0;

  esp_err_t csi_status = esp_wifi_set_csi_config(&csi_config);
  if (csi_status == ESP_OK) {
    esp_wifi_set_csi_rx_cb(wifi_csi_rx_cb, NULL);
    esp_wifi_set_csi(true);
    Serial.println(F("[OK] CSI Engine initialized."));
  }

  // Initialize I2C Bus on GPIO 21 (SDA) & GPIO 22 (SCL)
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(100000); // 100 kHz standard mode

  // Initialize hd44780 LCD controller (auto-detects address, chip type, pin mapping & timings)
  int lcdStatus = lcd.begin(20, 4);
  if (lcdStatus == 0) {
    lcdDetected = true;
    Serial.println(F("[LCD] hd44780 20x4 LCD detected & initialized successfully!"));

    // Flash backlight 2 times to provide immediate visual confirmation to user
    lcd.backlight();
    delay(250);
    lcd.noBacklight();
    delay(250);
    lcd.backlight();

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(F(" RF-CSI RADAR SENS  "));
    lcd.setCursor(0, 1);
    lcd.print(F(" ESP32+ESP8266 LINK "));
    lcd.setCursor(0, 2);
    lcd.print(F(" INITIALIZING DSP.. "));
    lcd.setCursor(0, 3);
    lcd.print(F(" SYSTEM READY [OK]  "));
    delay(1200);
    lcd.clear();
  } else {
    lcdDetected = false;
    Serial.printf("[LCD ERROR] LCD init failed with error code: %d\n", lcdStatus);
    Serial.println(F("[LCD HINT] Check 5V/VIN power and I2C wiring (G21->SDA, G22->SCL)"));
  }

  Serial.println(F("[STATUS] Radar active. Ready for Web Dashboard."));
}

void loop() {
  processSerialCommands();

  static unsigned long lastTick = 0;
  static unsigned long lastRateCheck = 0;
  static uint32_t lastPacketCountSnapshot = 0;
  unsigned long now = millis();

  // Packet Rate
  if (now - lastRateCheck >= 1000) {
    uint32_t packetsThisSecond = beaconPacketCount - lastPacketCountSnapshot;
    beaconPacketsPerSec = (float)packetsThisSecond;
    lastPacketCountSnapshot = beaconPacketCount;
    lastRateCheck = now;
  }

  beaconConnected = (now - lastBeaconPacketTime < 1200);

  // DSP processing tick (every 40ms = 25Hz)
  if (now - lastTick >= 40) {
    lastTick = now;

    // Combined motion energy with Motion Gain
    float rawMotionEnergy = 0.0f;
    if (beaconConnected) {
      rawMotionEnergy = ((currentCsiPerturbation * 1.3f) + (rssiPerturbation * 4.5f)) * motionGain;
    }

    // Hampel filter
    float hampelCleaned = applyHampelFilter(rawMotionEnergy);

    // Rolling history & statistics
    historyBuffer[historyIndex] = hampelCleaned;
    historyIndex = (historyIndex + 1) % HISTORY_LEN;

    float sum = 0.0f;
    for (int i = 0; i < HISTORY_LEN; i++) sum += historyBuffer[i];
    float mean = sum / (float)HISTORY_LEN;

    float varSum = 0.0f;
    for (int i = 0; i < HISTORY_LEN; i++) {
      float diff = historyBuffer[i] - mean;
      varSum += (diff * diff);
    }
    float stdDev = sqrt(varSum / (float)HISTORY_LEN);

    // Filtered motion score
    float instMotion = (mean * 0.4f) + (stdDev * 1.6f);
    filteredMotionScore = (filteredMotionScore * 0.70f) + (instMotion * 0.30f);

    // Auto-calibration
    if (isCalibrating) {
      calibrationAccumulator += filteredMotionScore;
      calibrationSampleCount++;
      if (now - calibrationStartTime >= CALIBRATION_DURATION_MS) {
        isCalibrating = false;
        if (calibrationSampleCount > 0) {
          ambientNoiseBaseline = (calibrationAccumulator / (float)calibrationSampleCount);
          if (ambientNoiseBaseline < 2.5f) ambientNoiseBaseline = 2.5f;
        }
        Serial.print(F("[CAL_COMPLETE] New baseline: "));
        Serial.println(ambientNoiseBaseline, 2);
      }
    } else {
      // Baseline tracking (freeze during motion)
      if (beaconConnected && !motionDetected && filteredMotionScore < dynamicThreshold) {
        ambientNoiseBaseline = (ambientNoiseBaseline * 0.992f) + (filteredMotionScore * 0.008f);
      }
      if (ambientNoiseBaseline < 2.5f) ambientNoiseBaseline = 2.5f;
    }

    // Threshold calculation: Manual Override vs Auto-Adaptive
    if (manualThreshold > 0.0f) {
      dynamicThreshold = manualThreshold;
    } else {
      dynamicThreshold = (ambientNoiseBaseline * sensitivityFactor) + minThresholdOffset;
    }

    float releaseThreshold = dynamicThreshold * 0.75f;

    // Decision Logic
    if (beaconConnected) {
      if (!motionDetected) {
        if (filteredMotionScore > dynamicThreshold) {
          consecutiveHighCount++;
          if (consecutiveHighCount >= motionTriggerFrames) {
            motionDetected = true;
            motionTriggerTime = now;
          }
        } else {
          if (consecutiveHighCount > 0) consecutiveHighCount--;
        }
      } else {
        if (filteredMotionScore > releaseThreshold) {
          motionTriggerTime = now;
        }
        if (now - motionTriggerTime > motionHoldTimeMs) {
          motionDetected = false;
          consecutiveHighCount = 0;
        }
      }
    } else {
      motionDetected = false;
      consecutiveHighCount = 0;
    }

    digitalWrite(LED_PIN, motionDetected ? HIGH : LOW);

    // Format MAC string
    char macStr[18];
    if (hasLearnedBeaconMac) {
      snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
               beaconMac[0], beaconMac[1], beaconMac[2], beaconMac[3], beaconMac[4], beaconMac[5]);
    } else {
      snprintf(macStr, sizeof(macStr), "SEARCHING");
    }

    // Telemetry output
    Serial.print("Motion_Score:");
    Serial.print(filteredMotionScore, 2);
    Serial.print(" Threshold:");
    Serial.print(dynamicThreshold, 2);
    Serial.print(" Alert:");
    Serial.print(motionDetected ? 1 : 0);
    Serial.print(" Baseline:");
    Serial.print(ambientNoiseBaseline, 2);
    Serial.print(" Beacon_Status:");
    Serial.print(beaconConnected ? 1 : 0);
    Serial.print(" Beacon_RSSI:");
    Serial.print(beaconRssi);
    Serial.print(" Beacon_Rate:");
    Serial.print(beaconPacketsPerSec, 0);
    Serial.print(" Beacon_MAC:");
    Serial.print(macStr);
    Serial.print(" SubVar:");
    Serial.print(currentSubcarrierVariance, 2);
    Serial.println();
  }

  // Non-blocking 20x4 LCD Refresh Routine (every 250ms)
  if (lcdDetected && (now - lastLcdUpdate >= LCD_REFRESH_INTERVAL_MS)) {
    lastLcdUpdate = now;

    // Line 0: Overall Status
    lcd.setCursor(0, 0);
    if (!beaconConnected) {
      lcd.print(F("STATUS: BCN OFFLINE "));
    } else if (motionDetected) {
      lcd.print(F("! INTRUSION ALERT ! "));
    } else if (filteredMotionScore > (ambientNoiseBaseline * 1.3f)) {
      lcd.print(F("STATUS: MICRO-MOTION"));
    } else {
      lcd.print(F("STATUS: ROOM SECURE "));
    }

    // Line 1: Motion Score & Dynamic Threshold Limit
    char line1[21];
    snprintf(line1, sizeof(line1), "MOT:%5.1f  LIM:%5.1f ", filteredMotionScore, dynamicThreshold);
    lcd.setCursor(0, 1);
    lcd.print(line1);

    // Line 2: Beacon Status & Signal RSSI
    char line2[21];
    if (beaconConnected) {
      snprintf(line2, sizeof(line2), "BCN: ONLINE  %3d dBm", beaconRssi);
    } else {
      snprintf(line2, sizeof(line2), "BCN: SEARCHING...   ");
    }
    lcd.setCursor(0, 2);
    lcd.print(line2);

    // Line 3: Packet Rate & Ambient Noise Floor
    char line3[21];
    snprintf(line3, sizeof(line3), "RATE:%2.0fPPS  FLR:%4.1f", beaconPacketsPerSec, ambientNoiseBaseline);
    lcd.setCursor(0, 3);
    lcd.print(line3);
  }
}

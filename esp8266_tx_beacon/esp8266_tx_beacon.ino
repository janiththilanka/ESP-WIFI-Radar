/*
 =====================================================================================
  ESP8266 Wi-Fi Motion Radar - Transmitter Node (RF Beacon)
 =====================================================================================
  Role: Continuous RF Pulse Transmitter
  Protocol: ESP-NOW (Broadcast: FF:FF:FF:FF:FF:FF)
  Channel: Fixed Wi-Fi Channel 1 (must match receiver)
  Rate: ~30-40 packets per second (OFDM 802.11g/n for CSI multipath scattering)
 =====================================================================================
*/

#include <ESP8266WiFi.h>
#include <espnow.h>
#include <user_interface.h>

// Wi-Fi Channel (1-13). MUST match on both ESP8266 and ESP32
#define RADAR_WIFI_CHANNEL 1

// Transmission interval in milliseconds (30ms = ~33 packets/second)
#define PULSE_INTERVAL_MS  30

// Broadcast address: targets any listening ESP32 receiver on the same channel
uint8_t broadcastMac[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// Radar pulse payload structure
typedef struct __attribute__((packed)) {
  uint32_t seqNumber;    // Monotonically increasing packet ID
  uint32_t timestamp;    // Milliseconds uptime
  char     signature[8]; // "WIFI_RAD"
} RadarPulsePacket;

RadarPulsePacket pulse;
unsigned long lastPulseTime = 0;
bool onboardLedState = false;

// Optional: Callback when packet sent
void onPacketSent(uint8_t *mac_addr, uint8_t sendStatus) {
  // sendStatus: 0 = success
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F(" ESP8266 Wi-Fi Motion Radar Transmitter "));
  Serial.println(F("========================================"));

  // Built-in LED on NodeMCU / D1 Mini (typically pin 2 or pin 16)
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // Turn off (active LOW)

  // Configure Wi-Fi in Station mode and disconnect from any AP
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // Force 802.11n / 802.11g PHY mode so packets use OFDM subcarriers (required for CSI)
  wifi_set_phy_mode(PHY_MODE_11N);

  // Set fixed Wi-Fi channel
  wifi_promiscuous_enable(1);
  wifi_set_channel(RADAR_WIFI_CHANNEL);
  wifi_promiscuous_enable(0);

  // Initialize ESP-NOW
  if (esp_now_init() != 0) {
    Serial.println(F("[ERROR] ESP-NOW initialization failed!"));
    return;
  }

  // Set role as Controller/Master
  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
  esp_now_register_send_cb(onPacketSent);

  // Register broadcast peer
  int addStatus = esp_now_add_peer(broadcastMac, ESP_NOW_ROLE_SLAVE, RADAR_WIFI_CHANNEL, NULL, 0);
  if (addStatus == 0) {
    Serial.print(F("[OK] ESP-NOW Peer registered. Channel: "));
    Serial.println(RADAR_WIFI_CHANNEL);
  } else {
    Serial.println(F("[WARN] Peer registration returned non-zero code."));
  }

  // Initialize payload signature
  strncpy(pulse.signature, "WIFI_RAD", sizeof(pulse.signature));
  pulse.seqNumber = 0;

  Serial.println(F("[STATUS] Transmitter active. Broadcasting radar pulses..."));
}

void loop() {
  unsigned long now = millis();

  if (now - lastPulseTime >= PULSE_INTERVAL_MS) {
    lastPulseTime = now;
    pulse.seqNumber++;
    pulse.timestamp = now;

    // Send packet via ESP-NOW
    esp_now_send(broadcastMac, (uint8_t *)&pulse, sizeof(pulse));

    // Heartbeat LED flash every 50 packets (~1.5s)
    if (pulse.seqNumber % 50 == 0) {
      digitalWrite(LED_BUILTIN, LOW);  // LED on
    } else if (pulse.seqNumber % 50 == 2) {
      digitalWrite(LED_BUILTIN, HIGH); // LED off
    }
  }

  yield();
}

# ThingSpeak Sensor Setup (BPM, EDA, Skin Temp, BVP)

This project now expects **ThingSpeak fields**:

- `field1` → BPM (heart rate)
- `field2` → EDA
- `field3` → Skin Temperature
- `field4` → BVP

The backend polls the latest feed while a session is in `recording` state, stores rows in:

- `datasets/compressed_<SID>_whole_df.csv`

## 1) Hardware wiring (ESP32 example)

> Use your exact sensor datasheets for voltage limits. The mapping below is a common starter pattern.

- **BPM analog output** → ESP32 `GPIO34` (ADC input)
- **EDA analog output** → ESP32 `GPIO35` (ADC input)
- **Skin temperature analog output** → ESP32 `GPIO32` (ADC input)
- **BVP analog output** → ESP32 `GPIO33` (ADC input)
- All sensor `GND` pins → ESP32 `GND`
- Sensor power → ESP32 `3V3` (or external regulated supply if required)

If your sensors are I2C/SPI modules, connect by protocol and compute exported values in firmware, then still publish to ThingSpeak fields 1-4.

## 2) ThingSpeak channel

Create one channel with 4 fields:

1. BPM
2. EDA
3. SkinTemp
4. BVP

Copy:
- **Channel ID**
- **Write API Key** (for ESP32)
- **Read API Key** (for backend, optional for public channel)

## 3) ESP32 firmware example (Arduino)

```cpp
#include <WiFi.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";
const char* TS_HOST = "api.thingspeak.com";
String TS_WRITE_KEY = "YOUR_THINGSPEAK_WRITE_KEY";

const int PIN_BPM  = 34; // field1
const int PIN_EDA  = 35; // field2
const int PIN_TEMP = 32; // field3
const int PIN_BVP  = 33; // field4

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

float readBpm() {
  int raw = analogRead(PIN_BPM);
  return map(raw, 0, 4095, 50, 120); // replace with real BPM algorithm
}

float readEda() {
  int raw = analogRead(PIN_EDA);
  return (raw / 4095.0f) * 6.0f; // example scaling
}

float readSkinTemp() {
  int raw = analogRead(PIN_TEMP);
  return 30.0f + (raw / 4095.0f) * 8.0f; // example 30-38°C
}

float readBvp() {
  int raw = analogRead(PIN_BVP);
  return (raw / 4095.0f) * 100.0f; // example scaling
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    if (client.connect(TS_HOST, 80)) {
      float bpm  = readBpm();
      float eda  = readEda();
      float temp = readSkinTemp();
      float bvp  = readBvp();

      String postData = "api_key=" + TS_WRITE_KEY +
                        "&field1=" + String(bpm, 2) +
                        "&field2=" + String(eda, 3) +
                        "&field3=" + String(temp, 2) +
                        "&field4=" + String(bvp, 2);

      client.println("POST /update HTTP/1.1");
      client.println("Host: api.thingspeak.com");
      client.println("Connection: close");
      client.println("Content-Type: application/x-www-form-urlencoded");
      client.print("Content-Length: ");
      client.println(postData.length());
      client.println();
      client.println(postData);
    }
    client.stop();
  }

  delay(15000); // ThingSpeak free tier: >= 15s update interval
}
```

## 4) Backend `.env` keys

Set these in your API `.env`:

```env
THINGSPEAK_CHANNEL_ID=YOUR_CHANNEL_ID
THINGSPEAK_READ_API_KEY=YOUR_READ_KEY
THINGSPEAK_POLL_SECONDS=2
THINGSPEAK_HR_FIELD=field1
THINGSPEAK_EDA_FIELD=field2
THINGSPEAK_TEMP_FIELD=field3
THINGSPEAK_BVP_FIELD=field4
```

## 5) Runtime flow

1. User clicks **Start Recording** in frontend.
2. Backend marks session as recording and starts ThingSpeak polling loop.
3. Values stream to WebSocket and append to local session CSV.
4. User clicks **Stop Recording**.
5. Backend marks session complete and triggers ML pipeline (`run_training_and_prediction`).
6. Predictions + recommendations are saved and visible in patient/doctor dashboards.


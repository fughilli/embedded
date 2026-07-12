// WiFi smoke test: bring up a soft-AP and serve a static hello-world page.
// ESP32-C6 only (the RP2350 board here has no radio support wired up).
//
// Join the AP below, then browse to http://192.168.4.1/. Note: phones that
// keep mobile data enabled may route around a WiFi network with no internet
// and time out — test with mobile data off, or use a laptop.
#include <Arduino.h>
#include <WebServer.h>
#include <WiFi.h>

static const char *kSsid = "esp32c6-hello";
static const char *kPassword = "helloworld";

static WebServer server(80);
static bool ap_up = false;

static const char kPage[] =
    "<!DOCTYPE html><html><head><title>ESP32-C6</title></head>"
    "<body><h1>Hello, world!</h1>"
    "<p>Served by an ESP32-C6 built with Bazel.</p></body></html>";

void setup() {
  Serial.begin(115200);
  ap_up = WiFi.softAP(kSsid, kPassword);
  if (ap_up) {
    server.on("/", []() { server.send(200, "text/html", kPage); });
    server.begin();
  }
}

void loop() {
  server.handleClient();
  // Status heartbeat rather than a one-shot setup() print: USB-Serial/JTAG
  // re-enumerates on reset, so a monitor attached after boot misses setup().
  static uint32_t last_report_ms = 0;
  if (millis() - last_report_ms > 5000) {
    last_report_ms = millis();
    if (ap_up) {
      Serial.printf("[wifi_ap] AP \"%s\" up, %d station(s), http://%s/\n",
                    kSsid, WiFi.softAPgetStationNum(),
                    WiFi.softAPIP().toString().c_str());
    } else {
      Serial.println("[wifi_ap] softAP() FAILED");
    }
  }
  delay(2);
}

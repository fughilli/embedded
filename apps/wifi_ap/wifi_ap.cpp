// WiFi smoke test: soft-AP + webserver with a color picker webapp (page.html,
// embedded via c_resource_library) that drives the onboard WS2812 LED.
// ESP32-C6 only (the RP2350 board here has no radio support wired up).
//
// Join the AP below, browse to http://192.168.4.1/, and pick a color. Note:
// phones that keep mobile data enabled may route around a WiFi network with
// no internet and time out — disable mobile data or accept the "no internet,
// stay connected?" prompt.
#include <Arduino.h>
#include <WebServer.h>
#include <WiFi.h>

#include "apps/wifi_ap/page.h"
#include "libs/pins/pins.h"

static const char *kSsid = "esp32c6-hello";
static const char *kPassword = "helloworld";

static WebServer server(80);
static bool ap_up = false;

static void handle_led() {
  String c = server.arg("c");
  if (c.length() != 6) {
    server.send(400, "text/plain", "want c=RRGGBB");
    return;
  }
  uint32_t rgb = strtoul(c.c_str(), nullptr, 16);
  rgbLedWrite(LED_DATA_PIN, (rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff);
  server.send(200, "text/plain", "ok");
}

void setup() {
  Serial.begin(115200);
  rgbLedWrite(LED_DATA_PIN, 0, 0, 0);
  ap_up = WiFi.softAP(kSsid, kPassword);
  if (ap_up) {
    server.on("/", []() { server.send(200, "text/html", page_html); });
    server.on("/led", handle_led);
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

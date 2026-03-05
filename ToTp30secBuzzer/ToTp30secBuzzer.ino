#include <WiFi.h>
#include "time.h"
#include <mbedtls/md.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

// --- CONFIGURATION ---
#define DEVICE_NAME "B_106"
#define LED_PIN 21             // XIAO S3 LED is Active LOW
#define BUZZER_PIN 1           // D0 on XIAO ESP32-S3 is GPIO 1
const char* ssid     = "g965g"; 
const char* password = "chetan12";

BLEAdvertising *pAdvertising;
unsigned long lastUpdate = 0;

// --- SHA-256 HASHING LOGIC ---
uint32_t generateTOTP() {
    time_t now;
    time(&now);
    uint32_t timeStep = now / 30; 
    
    String input = String(DEVICE_NAME) + String(timeStep);
    
    byte shaResult[32];
    mbedtls_md_context_t ctx;
    mbedtls_md_init(&ctx);
    mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 0);
    mbedtls_md_starts(&ctx);
    mbedtls_md_update(&ctx, (const unsigned char*) input.c_str(), input.length());
    mbedtls_md_finish(&ctx, shaResult);
    mbedtls_md_free(&ctx);

    uint32_t hashInt = (shaResult[0] << 24) | (shaResult[1] << 16) | (shaResult[2] << 8) | shaResult[3];
    return hashInt % 100000000; 
}

void updateAdvertising() {
    // 1-second Beep and LED flash for new code
    digitalWrite(LED_PIN, LOW);    // LED ON
    digitalWrite(BUZZER_PIN, HIGH); // Buzzer ON
    
    pAdvertising->stop();
    delay(100); 

    uint32_t currentCode = generateTOTP();
    Serial.printf(">>> NEW TOKEN: %08u\n", currentCode);

    BLEAdvertisementData oAdvertisementData = BLEAdvertisementData();
    oAdvertisementData.setFlags(0x06); 
    oAdvertisementData.setName(DEVICE_NAME);
    
    String strData = "";
    strData += (char)0xFF; strData += (char)0xFF; 
    strData += (char)((currentCode >> 24) & 0xFF);
    strData += (char)((currentCode >> 16) & 0xFF);
    strData += (char)((currentCode >> 8) & 0xFF);
    strData += (char)(currentCode & 0xFF);
    oAdvertisementData.setManufacturerData(strData);

    pAdvertising->setAdvertisementData(oAdvertisementData);
    
    BLEAdvertisementData oScanResponse = BLEAdvertisementData();
    oScanResponse.setName(DEVICE_NAME);
    pAdvertising->setScanResponseData(oScanResponse);

    pAdvertising->start();
    
    delay(1000); // Wait for 1 second
    digitalWrite(LED_PIN, HIGH);   // LED OFF
    digitalWrite(BUZZER_PIN, LOW);  // Buzzer OFF
}

void setup() {
  Serial.begin(115200);
  
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Start with everything OFF (LED HIGH is OFF on XIAO S3)
  digitalWrite(LED_PIN, HIGH); 
  digitalWrite(BUZZER_PIN, LOW); 

  // 1. WiFi Connection Attempt
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  
  int retryCount = 0;
  // Try connecting for ~15 seconds (30 * 500ms)
  while (WiFi.status() != WL_CONNECTED && retryCount < 30) { 
    delay(500); 
    Serial.print("."); 
    retryCount++;
  }

  // --- ERROR CHECK: IF WIFI FAILED ---
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi Connection FAILED!");
    Serial.println("System Halted. LED is ON.");
    
    digitalWrite(LED_PIN, LOW); // Turn LED ON permanently
    while(1) {
      // Do nothing forever - Block further execution
      delay(1000);
    }
  }

  // --- PROCEED ONLY IF WIFI CONNECTED ---
  Serial.println("\nWiFi Connected!");
  
  // 3-second Beep for connection success
  digitalWrite(BUZZER_PIN, HIGH);
  delay(3000);
  digitalWrite(BUZZER_PIN, LOW);

  // 2. Sync Time
  configTime(19800, 0, "pool.ntp.org", "time.google.com"); 
  struct tm timeinfo;
  Serial.print("Syncing Time");
  int timeRetry = 0;
  while(!getLocalTime(&timeinfo) && timeRetry < 20){ 
    delay(500); 
    Serial.print(".");
    timeRetry++;
  }
  Serial.println("\nTime Synced.");
  
  // 3. Kill WiFi (Important for BLE stability and power)
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  Serial.println("WiFi OFF. Starting BLE...");

  // 4. Init BLE
  BLEDevice::init(DEVICE_NAME);
  pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->setMinInterval(0x64); 
  pAdvertising->setMaxInterval(0x64);

  updateAdvertising();
  lastUpdate = millis();
}

void loop() {
  // Update every 30 seconds
  if (millis() - lastUpdate > 30000) {
    updateAdvertising();
    lastUpdate = millis();
  }
  delay(100);
}
#ifndef DISPLAY128_64_H
#define DISPLAY128_64_H

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>

//SPI
#define OLED_CS    1
#define OLED_DC    9
#define OLED_RST   10
#define OLED_MOSI  11
#define OLED_SCLK  12

class display128_64 {
public:
    display128_64();

    bool begin();
    void displayClear();
    
    void displayPrint(uint8_t linha, String texto, uint8_t tamanho = 1);

private:
    Adafruit_SSD1306 _display;
    const uint8_t _alturaLinha = 8; 
    void _fixAcentos(String &s);
};

#endif // DISPLAY128_64_H
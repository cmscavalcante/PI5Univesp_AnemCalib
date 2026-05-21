#include "display128_64.h"

display128_64::display128_64() 
    : _display(128, 64, OLED_MOSI, OLED_SCLK, OLED_DC, OLED_RST, OLED_CS) {}

bool display128_64::begin() {
    if (!_display.begin(SSD1306_SWITCHCAPVCC)) {
        return false;
    }

    _display.clearDisplay();
    _display.setTextSize(1);
    _display.cp437(true);
    _display.setTextColor(SSD1306_WHITE, SSD1306_BLACK); 
    
    _display.setTextWrap(false);
    _display.setCursor(0, 0);
    _display.display();
    return true;
}

void display128_64::displayClear() {
    _display.clearDisplay();
    _display.setCursor(0, 0);
    _display.display();
}

void display128_64::displayPrint(uint8_t linha, String texto, uint8_t tamanho) {
    if (linha > 7) linha = 7; 

    _fixAcentos(texto);
    _display.setTextSize(tamanho);
    _display.setCursor(0, linha * _alturaLinha);
    _display.print(texto);
    _display.display();
}


void display128_64::_fixAcentos(String &s) {
    String out = "";
    for (int i = 0; i < s.length(); i++) {
        unsigned char c = s[i];
        if (c < 128) {
            out += (char)c;
        } else if (c == 0xC3) { 
            i++;
            c = s[i];
            switch (c) {
                case 0xA1: out += (char)0xA0; break; // á
                case 0xA9: out += (char)0x82; break; // é
                case 0xAD: out += (char)0xA1; break; // í
                case 0xB3: out += (char)0xA2; break; // ó
                case 0xBA: out += (char)0xA3; break; // ú
                case 0xA3: out += (char)0x41; break; // ã -> A 
                case 0xB5: out += (char)0x4F; break; // õ -> O
                case 0xA7: out += (char)0x87; break; // ç
                default:   out += "?"; break;
            }
        }
    }
    s = out;
}
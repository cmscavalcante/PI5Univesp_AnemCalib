#include "gps.h"

ModuloGPS::ModuloGPS(int8_t rx, int8_t tx) : _rx(rx), _tx(tx) {
    _serialGPS = &Serial2; 
}

void ModuloGPS::enviarComandoUBX(byte* comando, int tamanho) {
    for (int i = 0; i < tamanho; i++) {
        _serialGPS->write(comando[i]);
    }
}

bool ModuloGPS::begin(unsigned long baud) {
    Serial1.begin(baud, SERIAL_8N1, _rx, _tx);
    _serialGPS = &Serial1;
    // Comando UBX-CFG-RATE para 2Hz (500ms)
    byte set2Hz[] = {0xB5, 0x62, 0x06, 0x08, 0x06, 0x00, 0xF4, 0x01, 0x01, 0x00, 0x01, 0x00, 0x0B, 0x77};
    enviarComandoUBX(set2Hz, sizeof(set2Hz));

    // Desativa sentenças NMEA pesadas para otimizar 9600bps
    byte disableGSV[] = {0xB5, 0x62, 0x06, 0x01, 0x08, 0x00, 0xF0, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x38};
    enviarComandoUBX(disableGSV, sizeof(disableGSV));

    byte disableGLL[] = {0xB5, 0x62, 0x06, 0x01, 0x08, 0x00, 0xF0, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2A};
    enviarComandoUBX(disableGLL, sizeof(disableGLL));
    
    _serialGPS->flush();
    delay(200);
    while(_serialGPS->available()) _serialGPS->read(); 
    _gps = TinyGPSPlus();

    unsigned long inicio = millis();
    while (millis() - inicio < 3000) {
        if (_serialGPS->available() > 0) {
            _gps.encode(_serialGPS->read());
            if (_gps.charsProcessed() > 10) return true;
        }
    }
    return false;
}

void ModuloGPS::update() {
    while (_serialGPS->available() > 0) {
        _gps.encode(_serialGPS->read());
    }
}

bool ModuloGPS::temFix() {
    return _gps.location.isValid() && _gps.location.age() < 15000;
}

float ModuloGPS::getHDOP() {
    return _gps.hdop.isValid() ? _gps.hdop.hdop() : 99.9f;
}

float ModuloGPS::getLatitude() { return _gps.location.lat(); }
float ModuloGPS::getLongitude() { return _gps.location.lng(); }

float ModuloGPS::getVelocidadeKmH() {
    float velBruta = _gps.speed.kmph();
    if (getHDOP() > _HDOP_MAXIMO || _gps.satellites.value() < 4) {
        _velocidadeSuave = 0.0f;
        return 0.0f;
    }
    if (velBruta < _CORTE_VELOCIDADE) velBruta = 0.0f;
    _velocidadeSuave = (0.1f * velBruta) + (0.9f * _velocidadeSuave);
    return _velocidadeSuave;
}

uint32_t ModuloGPS::getSatelites() { return _gps.satellites.value(); }
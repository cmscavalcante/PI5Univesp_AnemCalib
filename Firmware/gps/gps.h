#ifndef GPS_H
#define GPS_H

#include <Arduino.h>
#include <TinyGPS++.h>

class ModuloGPS {
public:
    ModuloGPS(int8_t rx, int8_t tx);
    bool begin(unsigned long baud = 9600); 
    void update();

    bool temFix();
    float getLatitude();
    float getLongitude();
    float getHDOP();
    float getVelocidadeKmH();
    float getGLocal() { return _gLocal; }
    void setGLocal(float g) { _gLocal = g; }
    uint32_t getSatelites();
    
    TinyGPSPlus& getParser() { return _gps; }

private:
    void enviarComandoUBX(byte* comando, int tamanho);
    int8_t _rx, _tx;
    TinyGPSPlus _gps;
    const float _HDOP_MAXIMO = 1.5f;
    const float _CORTE_VELOCIDADE = 2.0f;
    float _velocidadeSuave = 0.0f;
    float _gLocal = 9.80665f;
    HardwareSerial* _serialGPS;
};

#endif // GPS_H
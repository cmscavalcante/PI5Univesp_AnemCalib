#ifndef ACELEROMETRO_H
#define ACELEROMETRO_H

#include <MPU6050_tockn.h>
#include <Wire.h>

class Acelerometro {
public:
    Acelerometro();

    bool begin();
    void update(float velocidadeGPS); // Recebe a velocidade do GPS para adaptar o filtro
    void setGLocal(float g) { _gLocalInterno = g; }
    // Getters
    float getAccelYFiltrado() { return _valorFiltrado; }
    float getAccelYBruta() { return (_mpu.getAccY() * 9.80665f) - _offsetY; }
    float getAccelX() { return (_mpu.getAccX() - _offsetX) * _gLocalInterno; }
    float getAccelY() { return (_mpu.getAccY() - _offsetY) * _gLocalInterno; }
    float getAccelZ() { 
        float leituraZ = _mpu.getAccZ() * _gLocalInterno;
        float offsetZ_ms2 = _offsetZ * _gLocalInterno;
        return (offsetZ_ms2 - leituraZ); 
    }
private:
    MPU6050 _mpu;
    float _accYFiltrada;
    // Variáveis de controle do filtro
    float _valorFiltrado;
    float _offsetX, _offsetY, _offsetZ;
    float _gLocalInterno = 9.80665f; // Valor padrão inicial
    float _limiteGatilho; // Valor em m/s² que aciona o filtro
};

#endif // ACELEROMETRO_H
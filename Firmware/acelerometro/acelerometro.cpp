#include "acelerometro.h"

Acelerometro::Acelerometro() : _mpu(Wire) {
    _valorFiltrado = 0;
    _offsetY = 0;
    _limiteGatilho = 0.5f;
}

bool Acelerometro::begin() {
    _mpu.begin();

    // Configura o filtro DLPF para 5Hz para estabilidade
    Wire.beginTransmission(0x68);
    Wire.write(0x1A); 
    Wire.write(0x06); 
    Wire.endTransmission();

    _mpu.calcGyroOffsets(true); // Calibra Giroscópio

    float sX = 0, sY = 0, sZ = 0;
    const int amostras = 200;

    for(int i = 0; i < amostras; i++) {
        _mpu.update();
        sX += _mpu.getAccX();
        sY += _mpu.getAccY();
        sZ += _mpu.getAccZ();
        delay(3);
    }

    _offsetX = sX / amostras;
    _offsetY = sY / amostras;
    // O offset de Z remove a aceleração estática de 1g lida pelo sensor
    _offsetZ = sZ / amostras; 

    return true;
}

void Acelerometro::update(float velocidadeGPS) {
    _mpu.update();

    // 1. Acelerações descontadas o bias
    float accX = (_mpu.getAccX() - _offsetX) * _gLocalInterno;
    float accY = (_mpu.getAccY() - _offsetY) * _gLocalInterno;
    float accZ = (_offsetZ - _mpu.getAccZ()) * _gLocalInterno;

    // 2. Cálculo do módulo do movimento
    float magnitudeReal = sqrt(accX*accX + accY*accY + accZ*accZ);

    float alpha;

    // 3. LÓGICA DE BURST DINÂMICA
    if (velocidadeGPS < 0.5f) {
        // VEÍCULO PARADO: Filtro muito pesado para estabilizar o zero
        alpha = 0.005f;
        
        // GATILHO: Se a magnitude exceder o limite, o filtro é aliviado
        if (magnitudeReal > 1.2f) { // 1.2 m/s2 é uma aceleração compatível com uma rajada
            alpha = 0.20f; // Modo Burst: resposta rápida ao início do movimento
        }
    } else {
        // VEÍCULO EM MOVIMENTO: Filtro equilibrado
        if (magnitudeReal > 0.8f) {
            alpha = 0.15f; // Burst para capturar variações rápidas
        } else {
            alpha = 0.08f; // Suavização normal de cruzeiro
        }
    }

    // 4. Aplica o filtro EMA na aceleração
    _valorFiltrado = (alpha * accY) + ((1.0f - alpha) * _valorFiltrado);
}
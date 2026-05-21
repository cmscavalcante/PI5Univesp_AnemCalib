#include "compGravity.h"
#include <math.h>

compGravity::compGravity() : _nivelZero(9.80665f) {}

float compGravity::calcularGLocal(float latitude, float altitude) {
    float rad = latitude * M_PI / 180.0f;
    float g = 9.780327f * (1.0f + 0.0053024f * pow(sin(rad), 2) - 0.0000058f * pow(sin(2.0f * rad), 2));
    g -= 0.000003086f * altitude;
    return g;
}

void compGravity::calibrar(float ax, float ay, float az, float gReferencia) {
    // Calcula a magnitude total lida pelo sensor (independente da inclinação)
    float moduloLido = sqrt(ax * ax + ay * ay + az * az);
    
    // Normalização: Vetor unitário que descreve a direção da gravidade
    // Se o sensor está inclinado, ax e ay não serão zero, e esses valores
    // guardarão a proporção exata da inclinação.
    _calibX = ax / moduloLido;
    _calibY = ay / moduloLido;
    _calibZ = az / moduloLido;
    
    // Se está disponível o G-Local do GPS, usa como alvo real, 
    // senão usa o próprio módulo lido.
    _nivelZero = (gReferencia > 0) ? gReferencia : moduloLido;
    
    Serial.printf("Orientacao Aprendida -> X:%.3f Y:%.3f Z:%.3f\n", _calibX, _calibY, _calibZ);
}

void compGravity::calibrarSuave(float ax, float ay, float az, float gReferencia, float alpha) {
    float moduloLido = sqrt(ax * ax + ay * ay + az * az);
    
    // Alpha passado para decidir quão rápido o horizonte se ajusta
    _calibX = (alpha * (ax / moduloLido)) + ((1.0f - alpha) * _calibX);
    _calibY = (alpha * (ay / moduloLido)) + ((1.0f - alpha) * _calibY);
    _calibZ = (alpha * (az / moduloLido)) + ((1.0f - alpha) * _calibZ);
    
    _nivelZero = (alpha * gReferencia) + ((1.0f - alpha) * _nivelZero);
}

float compGravity::obterAceleracaoLinear(float ax, float ay, float az) {
    // PRODUTO ESCALAR: Projeta o vetor de aceleração atual sobre o eixo da gravidade aprendida
    float componenteVertical = (ax * _calibX) + (ay * _calibY) + (az * _calibZ);
    float resultado = componenteVertical - _nivelZero;
    if (abs(resultado) < 0.20f) return 0.0f;
    return resultado;
}
#ifndef COMP_GRAVITY_H
#define COMP_GRAVITY_H

#include <Arduino.h>

class compGravity {
public:
    compGravity();
    float calcularGLocal(float latitude, float altitude);
    void calibrar(float ax, float ay, float az, float gReferencia = 0);
    float obterAceleracaoLinear(float ax, float ay, float az);
    void calibrarSuave(float ax, float ay, float az, float gReferencia, float alpha = 0.05f);

private:
    float _nivelZero;
    // Coeficientes de orientação (Vetor Unitário da Gravidade)
    float _calibX = 0;
    float _calibY = 0;
    float _calibZ = 1.0f; 
};

#endif // COMP_GRAVITY_H
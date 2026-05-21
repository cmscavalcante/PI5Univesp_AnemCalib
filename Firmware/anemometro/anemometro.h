#ifndef ANEMOMETRO_H
#define ANEMOMETRO_H

#include <Arduino.h>

class Anemometro {
public:
    Anemometro(
        uint8_t pin,
        float fatorCalibracao = 1.0f,
        uint8_t pulsosPorVolta = 3
    );

    void begin();
    void atualizar();

    float getHz() const;
    float getRPM() const;
    float getVelocidade() const;

private:
    static void IRAM_ATTR isr();

    static volatile uint32_t _ultimoPulso;
    static volatile uint32_t _periodo;

    static Anemometro* _instancia;

    uint8_t _pin;
    uint8_t _pulsosPorVolta;

    float _fatorCalibracao;

    float _hz;
    float _rpm;
    float _velocidade;

    uint32_t _timeoutMicros;

    // rejeita glitches
    static uint32_t _periodoMinimo;
};

#endif // ANEMOMETRO_H


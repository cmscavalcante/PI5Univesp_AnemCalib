#include "anemometro.h"

volatile uint32_t Anemometro::_ultimoPulso = 0;
volatile uint32_t Anemometro::_periodo = 120000;
uint32_t Anemometro::_periodoMinimo = 500;

Anemometro* Anemometro::_instancia = nullptr;

Anemometro::Anemometro(
    uint8_t pin,
    float fatorCalibracao,
    uint8_t pulsosPorVolta
)
{
    _pin = pin;
    _fatorCalibracao = fatorCalibracao;
    _pulsosPorVolta = pulsosPorVolta;

    _hz = 0.0f;
    _rpm = 0.0f;
    _velocidade = 0.0f;

    _timeoutMicros = 2000000;

    // ignora períodos menores que 500 µs
    _periodoMinimo = 500;

    _instancia = this;
}

void Anemometro::begin()
{
    pinMode(_pin, INPUT_PULLUP);

    attachInterrupt(
        digitalPinToInterrupt(_pin),
        isr,
        RISING
    );
}

void IRAM_ATTR Anemometro::isr()
{
    uint32_t agora = micros();

    // primeira borda
    if (_ultimoPulso == 0) {
        _ultimoPulso = agora;
        return;
    }

    uint32_t dt = agora - _ultimoPulso;

    // rejeita pulsos impossíveis
    if (dt < _periodoMinimo) {
        return;
    }

    // rejeita glitches relativos
    if (dt < (_periodo / 3)) {
        return;
    }

    _periodo = dt;
    _ultimoPulso = agora;
}

void Anemometro::atualizar()
{
    uint32_t periodo;
    uint32_t ultimoPulso;

    noInterrupts();
    periodo = _periodo;
    ultimoPulso = _ultimoPulso;
    interrupts();

    uint32_t agora = micros();

    // timeout = parado
    if ((agora - ultimoPulso) > _timeoutMicros) {

        _hz = 0.0f;
        _rpm = 0.0f;
        _velocidade = 0.0f;

        return;
    }

    if (periodo == 0) {
        return;
    }

    _hz = 1000000.0f / (float)periodo;

    _rpm = (_hz * 60.0f) / (float)_pulsosPorVolta;

    _velocidade = _rpm * _fatorCalibracao;
}

float Anemometro::getHz() const
{
    return _hz;
}

float Anemometro::getRPM() const
{
    return _rpm;
}

float Anemometro::getVelocidade() const
{
    return _velocidade;
}
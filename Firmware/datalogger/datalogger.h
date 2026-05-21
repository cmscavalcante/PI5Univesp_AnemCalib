#ifndef DATALOGGER_H
#define DATALOGGER_H

#include <Arduino.h>
#include "FS.h"
#include "SD_MMC.h"

class Datalogger {
public:
    bool begin(uint8_t clk, uint8_t cmd, uint8_t d0);
    void criarCabecalho();
    void gravarDados(String tempoGps, float freq, float rpm, float vGps, 
                     float ax, float ay, float az, float gLocal, float altitude);
    void listarArquivosSerial();
    bool transmitirArquivo(String nome);
    bool formatarOuApagarTudo();

private:
    String _nomeArquivo = "/log_vento.csv";
};

#endif // DATALOGGER_H
#ifndef SERIAL_HANDLER_H
#define SERIAL_HANDLER_H

#include <Arduino.h>
#include "datalogger/datalogger.h"

class SerialHandler {
public:
    SerialHandler(bool& gravandoLog, const bool& sdOk, Datalogger& logger);
    void update();

private:
    bool& _gravandoLog;
    const bool& _sdOk;
    Datalogger& _logger;
    bool _aguardandoConfirmacaoApagar = false;

    void processarComando(String cmd);
    void apagarTudo();
};

#endif // SERIAL_HANDLER_H
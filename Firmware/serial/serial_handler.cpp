#include "serial_handler.h"

SerialHandler::SerialHandler(bool& gravandoLog, const bool& sdOk, Datalogger& logger) 
    : _gravandoLog(gravandoLog), _sdOk(sdOk), _logger(logger) {}

void SerialHandler::update() {
    if (Serial.available() > 0) {
        String comando = Serial.readStringUntil('\n');
        comando.trim();
        if (comando.length() > 0) processarComando(comando);
    }
}

void SerialHandler::processarComando(String cmd) {
    // Lógica de confirmação para ERASE_ALL
    if (_aguardandoConfirmacaoApagar) {
        if (cmd == "S" || cmd == "s") {
            apagarTudo();
        } else {
            Serial.println("RES:ERASE_CANCELLED");
        }
        _aguardandoConfirmacaoApagar = false;
        return;
    }

    // Dicionário de Comandos
    if (cmd == "START") {
        if (_sdOk) { _gravandoLog = true; Serial.println("RES:START_CONFIRMED"); }
        else { Serial.println("RES:START_FAILED"); }
    } 
    else if (cmd == "STOP") {
        _gravandoLog = false;
        Serial.println("RES:STOP_CONFIRMED");
    } 
    else if (cmd == "GET_FILES") {
        _logger.listarArquivosSerial(); 
    } 
    else if (cmd.startsWith("SEND_FILE:")) {
        if (_gravandoLog) { Serial.println("RES:ERROR_BUSY"); }
        else { _logger.transmitirArquivo(cmd.substring(10)); }
    }
    else if (cmd == "ERASE_ALL") {
        if (_gravandoLog) { Serial.println("RES:ERROR_BUSY"); }
        else {
            _aguardandoConfirmacaoApagar = true;
            Serial.println("RES:CONFIRM_ERASE_S/N");
        }
    }
}

void SerialHandler::apagarTudo() {
    if (!_sdOk) { Serial.println("RES:SD_ERROR"); return; }
    if (_logger.formatarOuApagarTudo()) { Serial.println("RES:ERASE_SUCCESS"); }
    else { Serial.println("RES:ERASE_FAILED"); }
}
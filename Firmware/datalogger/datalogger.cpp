#include "Datalogger.h"

bool Datalogger::begin(uint8_t clk, uint8_t cmd, uint8_t d0) {
    if (!SD_MMC.setPins(clk, cmd, d0)) return false;
    return SD_MMC.begin("/sdcard", true); // Modo 1-bit para S3-CAM
}

void Datalogger::criarCabecalho() {
    File arquivo = SD_MMC.open(_nomeArquivo, FILE_WRITE);
    if (arquivo) {
        // Cabeçalho expandido
        arquivo.println("timestamp_ms;freq_hz;rpm;v_gps_kmh;accx;accy;accz;g_local;altitude");
        arquivo.close();
    }
}

void Datalogger::gravarDados(String tempoGps, float freq, float rpm, float vGps, 
                             float ax, float ay, float az, float gLocal, float altitude) {
    File arquivo = SD_MMC.open(_nomeArquivo, FILE_APPEND);
    if (arquivo) {
        arquivo.print(tempoGps);      arquivo.print(";"); // Tempo UTC do GPS
        arquivo.print(freq, 2);       arquivo.print(";");
        arquivo.print(rpm, 0);        arquivo.print(";");
        arquivo.print(vGps, 2);       arquivo.print(";");
        arquivo.print(ax, 4);         arquivo.print(";");
        arquivo.print(ay, 4);         arquivo.print(";");
        arquivo.print(az, 4);         arquivo.print(";");
        arquivo.print(gLocal, 4);     arquivo.print(";");
        arquivo.println(altitude, 2);
        arquivo.close();
    }
}

void Datalogger::listarArquivosSerial() {
    File root = SD_MMC.open("/");
    File file = root.openNextFile();
    while(file) {
        Serial.print("RES:FILE:"); Serial.print(file.name());
        Serial.print("|SIZE:"); Serial.println(file.size());
        file = root.openNextFile();
    }
}

bool Datalogger::transmitirArquivo(String nome) {
    File f = SD_MMC.open("/" + nome, FILE_READ);
    if(!f) return false;
    
    Serial.println("RES:TRANSFER_START:" + nome);
    while(f.available()) {
        Serial.write(f.read()); // Transmissão binária ou texto
    }
    Serial.println("\nRES:TRANSFER_END");
    f.close();
    return true;
}

bool Datalogger::formatarOuApagarTudo() {
    File root = SD_MMC.open("/");
    if (!root || !root.isDirectory()) return false;

    File file = root.openNextFile();
    while (file) {
        String nome = "/" + String(file.name());
        file.close(); // Fecha antes de apagar
        SD_MMC.remove(nome);
        file = root.openNextFile();
    }
    return true;
}
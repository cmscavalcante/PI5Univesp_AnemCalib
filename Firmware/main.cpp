#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <AsyncDelay.h>
#include <Adafruit_NeoPixel.h>

#include "anemometro/anemometro.h"
#include "acelerometro/acelerometro.h"
#include "display/display128_64.h"
#include "gps/gps.h"
#include "corrections/compGravity.h" 
#include "datalogger/datalogger.h"
#include "serial/serial_handler.h"

// Definições de Pinos
    //I2C
        #define SDA_PIN 4
        #define SCL_PIN 5

    //Botão
        #define PIN_BOTAO_LOG 17

    //Anemometro
        #define PIN_ANEMOMETRO GPIO_NUM_18

// Instâncias
    Anemometro vento(PIN_ANEMOMETRO, 1.0f, 3);
    ModuloGPS gps(15, 16); 
    Acelerometro mpu;
    display128_64 oled;
    compGravity corretor; 
    Datalogger logger;

// Controles de tempo e estados
    AsyncDelay delayAtualizaDados;
    AsyncDelay delayLeituraBotao;

//Garante que o flash da placa de desenvolvimento esteja apagado
    #define FLASH_LIGHT_PIN 48
    #define FLASH_PIXELS 1

//Variáveis globais
    bool mpuOk = false;
    bool oledOk = false;
    bool sdOk = false;
    bool gravandoLog = false;
    bool modoTeste = false; // Ativa o modo de teste para desenvolvimento
    float accExibicao = 0;
    unsigned long tempoParado = 0;    

    Adafruit_NeoPixel flashLight(FLASH_PIXELS, FLASH_LIGHT_PIN, NEO_RBG + NEO_KHZ800);
    SerialHandler serialCtrl(gravandoLog, sdOk, logger);


void setup() {
    Serial.begin(115200);
    Serial.println("RES:Iniciando sistema de calibração de anemômetro...");
    pinMode(PIN_BOTAO_LOG, INPUT_PULLUP);
    //Inicialiaza o flash e apaga.
    flashLight.begin();
    flashLight.clear();
    flashLight.setBrightness(0);
    flashLight.show();
    flashLight.clear();
    Wire.begin(SDA_PIN, SCL_PIN); 

    // --- ETAPA 1: INICIALIZAÇÃO DO DISPLAY ---
    oledOk = oled.begin();
    if (oledOk) {
        oled.displayClear();
        oled.displayPrint(0, "CALIBRACAO DE", 1);
        oled.displayPrint(1, "ANEMOMETRO", 1);
        oled.displayPrint(3, "Iniciando GPS...", 1);
    }

    // --- ETAPA 2: DATALOGGER ---
    sdOk = logger.begin(39, 38, 40); 

    if (sdOk) {
        logger.criarCabecalho();
        if (oledOk) oled.displayPrint(6, "SD MMC OK", 1);
        Serial.println("RES:Datalogger SD MMC inicializado com sucesso.");
    } else {
        if (oledOk) oled.displayPrint(6, "ERRO SD MMC", 1);
        Serial.println("RES:Erro ao inicializar o datalogger SD MMC.");
    }

    // --- ETAPA 2: SINAL DE SATÉLITE ---    
    Serial.println("RES:Inicializando GPS...");

    if (!gps.begin(9600)) {
        if (oledOk) oled.displayPrint(4, "RES:ERRO: GPS!", 2);
        while(1) { delay(1000); }
    }

    unsigned long timerOled = millis();
    
    // Laço de espera pelo fix do GPS, com opção de pular para Modo Teste se o botão for pressionado
    while (!gps.temFix() && !modoTeste) {
        gps.update(); 
        serialCtrl.update();
        if (digitalRead(PIN_BOTAO_LOG) == LOW) {
            modoTeste = true;
            Serial.println("RES:MODO_TESTE_ATIVADO");
            break;
        }
        if (millis() - timerOled > 500) {
            if (oledOk) {
                oled.displayClear();
                oled.displayPrint(0, "PRES. O BOTAO P/ TESTE",1);
                oled.displayPrint(1, "AGUARDANDO FIX", 1);
                oled.displayPrint(2, "Sats: " + String(gps.getSatelites()), 1);
            }
            Serial.println("RES:WAITING_GPS_SATS:" + String(gps.getSatelites()));
            timerOled = millis();
        }
        yield(); 
    }

    delay(2000); // Pausa para leitura do status SD

    // --- ETAPA 3: CALIBRAÇÃO DO ACELERÔMETRO ---
    if (oledOk) {
        oled.displayClear();
        if (modoTeste) {
            oled.displayPrint(0, "MODO TESTE!", 1);
        } else {
            oled.displayPrint(0, "GPS OK!", 1);
        }
        oled.displayPrint(2, "CALIBRANDO MPU", 1);
        Serial.println("RES:Calibrando MPU6050...");
        Serial.println("RES:Mantenha parado");
        oled.displayPrint(4, "MANTENHA PARADO", 1);
    }
    
    mpuOk = mpu.begin(); 
    if (mpuOk) {
        float gLocal = 9.80665; // Valor padrão caso esteja em Modo Teste
        
        if (!modoTeste) {
            // Se tiver GPS real, calcula a gravidade exata local
            gLocal = corretor.calcularGLocal(gps.getLatitude(), gps.getParser().altitude.meters());
            gps.setGLocal(gLocal); 
        } else {
            gps.setGLocal(gLocal); // Força o padrão no GPS fictício de bancada
        }
            
        float sX = 0, sY = 0, sZ = 0;
        const int leituras = 150; 

        for(int i = 0; i < leituras; i++) {
            mpu.update(0); 
            sX += mpu.getAccelX();
            sY += mpu.getAccelY();
            sZ += mpu.getAccelZ();
            delay(5);
        }
        
        // Faz a calibração inicial com a gravidade definida
        corretor.calibrar(sX/leituras, sY/leituras, sZ/leituras, gLocal);
    }

    // --- ETAPA 4: FINALIZAÇÃO ---
    vento.begin();
    
    if (oledOk) {
        oled.displayClear();
        if (modoTeste) {
            oled.displayPrint(1, "MODO TESTE", 1);
        }
        oled.displayPrint(3, "SISTEMA PRONTO", 1);
        oled.displayPrint(5, "Iniciando...", 1);
        delay(1500);
        oled.displayClear();
    }

    delayAtualizaDados.start(100, AsyncDelay::MILLIS);
    delayLeituraBotao.start(50, AsyncDelay::MILLIS);
}

void loop() {
    vento.atualizar();
    gps.update();
    serialCtrl.update(); // Gerencia comandos START, STOP, GET_FILES, SEND_FILE via Serial

    // --- TRATAMENTO DO BOTÃO FÍSICO ---
    if (delayLeituraBotao.isExpired()) {
        static bool estadoAnterior = HIGH;
        bool estadoAtual = digitalRead(PIN_BOTAO_LOG);

        if (estadoAnterior == HIGH && estadoAtual == LOW) { // Borda de descida (Pressionado)
            gravandoLog = !gravandoLog;

            if (gravandoLog) {
                // Se tentou iniciar mas o SD falhou
                if (!sdOk) {
                    gravandoLog = false;
                    Serial.println("RES:START_FAILED");
                } else {
                    Serial.println("RES:START_USER"); // Notifica o Tablet que iniciou pelo botão
                }
            } else {
                Serial.println("RES:STOP_USER"); // Notifica o Tablet que parou pelo botão
            }
        }
        estadoAnterior = estadoAtual;
        delayLeituraBotao.repeat();
        
        // Sincroniza G local entre GPS e MPU
        mpu.setGLocal(gps.getGLocal());
    }

    // --- PROCESSAMENTO E TRANSMISSÃO DE DADOS (10Hz) ---
    if (delayAtualizaDados.isExpired()) {
        // Captura de dados dos sensores
        float rpm = vento.getRPM();
        float freqHz = vento.getHz();
        float vGps = gps.getVelocidadeKmH();
        float alt = gps.getParser().altitude.meters();
        uint32_t sats = gps.getSatelites();
        float gpsGlocal = gps.getGLocal();

        // Recalibração dinâmica (Auto-Zero) quando parado
        if (vGps == 0.0f) {
            unsigned long agora = millis();
            if (tempoParado == 0) tempoParado = agora;
            float alphaDinamico = (agora - tempoParado < 2000) ? 0.20f : 0.02f;
            corretor.calibrarSuave(mpu.getAccelX(), mpu.getAccelY(), mpu.getAccelZ(), gpsGlocal, alphaDinamico);
        } else {
            tempoParado = 0;
        }

        // Processamento de Aceleração Linear
        mpu.update(vGps);
        float accInstantanea = corretor.obterAceleracaoLinear(mpu.getAccelX(), mpu.getAccelY(), mpu.getAccelZ());
        accExibicao = (0.2f * accInstantanea) + (0.8f * accExibicao);
        if (abs(accExibicao) < 0.1f) accExibicao = 0.0f;

        float accelX = mpu.getAccelX();
        float accelY = mpu.getAccelY();
        float accelZ = mpu.getAccelZ();

        // 1. GRAVAÇÃO NO SD (Condicional ao estado gravandoLog)
        if (gravandoLog && sdOk) {
            logger.gravarDados(String(millis()), freqHz, rpm, vGps, accelX, accelY, accelZ, gpsGlocal, alt);
        }

        // ENVIO PERMANENTE PARA O TABLET VIA SERIAL
        Serial.printf("%lu,%.1f,%.0f,%.1f,%.2f,%.2f,%.2f,%.3f,%u\n", 
                      millis(), freqHz, rpm, vGps, accelX, accelY, accelZ, gpsGlocal, sats);

        // --- ATUALIZAÇÃO DO DISPLAY OLED LOCAL ---
        if (modoTeste) {
            oled.displayPrint(0, "R:" + String(rpm, 0) + "RPM [TESTE] ", 1);
        } else {
            oled.displayPrint(0, "R:" + String(rpm, 0) + "RPM    ", 1);
        }

        oled.displayPrint(0, "R:" + String(rpm, 0) + "RPM    ", 1);
        oled.displayPrint(1, "f:" + String(freqHz, 1) + "Hz    ", 1);
        oled.displayPrint(2, "V:" + String(vGps, 1) + " km/h    ", 1);
        oled.displayPrint(3, "Ax:" + String(accelX, 2) + " m/s2    ", 1);
        oled.displayPrint(4, "Ay:" + String(accelY, 2) + " m/s2    ", 1);
        oled.displayPrint(5, "Az:" + String(accelZ, 2) + " m/s2    ", 1);
        oled.displayPrint(6, "G:" + String(gpsGlocal, 2) + " m/s2    ", 1);

        String statusStr = (gravandoLog ? "REC " : "STOP ") + String("S:") + String(sats);
        if (modoTeste) {
            Serial.print(freqHz); Serial.print(" Hz, ");Serial.print(rpm); Serial.println(" RPM, ");
            oled.displayPrint(7, statusStr + " M_TESTE      ", 1);
        } else {
            oled.displayPrint(7, statusStr + " H:" + String(gps.getHDOP(), 1), 1);
        }

        delayAtualizaDados.repeat();
    }
}


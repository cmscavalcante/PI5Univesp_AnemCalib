#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <SPI.h>
#include <mcp2515.h>


#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET    -1 
#define SCREEN_ADDRESS 0x3C // Endereço comum para 128x32

struct can_frame read_can_msg;
struct can_frame write_can_msg;

// Variáveis de Telemetria
unsigned long tempoUltimoRX = 0;   // Momento do último pacote recebido
unsigned long tempoAtualRX = 0;    // Momento do pacote atual
unsigned long intervaloEntreReq = 0; // Delta entre requisições
unsigned long latenciaResposta = 0;  // Tempo de processamento interno

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
MCP2515 mcp2515(10);

unsigned long tempoRX = 0; // Armazena o momento da chegada do pacote

const int potPin = A0;
int valorPot = 0;
int velocidade = 0;


void imprimirFrame(const char* direcao, const struct can_frame* frame);

void setup() {
  Serial.begin(115200);
  Serial.println(F("Iniciando OBD2 Simulator..."));
  // Inicializa o display
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("Falha ao iniciar o SSD1306"));
    for(;;); 
  }
  else {
    Serial.println(F("SSD1306 iniciado com sucesso"));
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 10);
  display.println(F("Simulador OBD2"));
  display.display();
  delay(2000);
  Serial.println(F("Iniciando MCP2515"));
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 10);
  display.println(F("Iniciando MCP2515"));
  display.display();
  delay(2000);
  mcp2515.reset();
  if (mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ) == MCP2515::ERROR_OK) {
    Serial.println(F("MCP2515 configurado para 500 kbps"));
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println(F("MCP2515 OK"));
    display.display();
  } else {
    Serial.println(F("Erro ao configurar o MCP2515"));
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println(F("MCP2515 ERRO"));
    display.display();
    for(;;); 
  }
  mcp2515.setNormalMode();
  delay(2000);
  Serial.println(F("\n--- MONITOR OBD2 ATIVO ---"));
  Serial.println(F("Formatado como: [SENTIDO] | ID | DLC | BYTES"));

}

void loop() {
  // Leitura e mapeamento
  valorPot = analogRead(potPin);
  velocidade = map(valorPot, 0, 1023, 0, 100);

  // Atualização do Display
  display.clearDisplay();
  
  // Rótulo
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(F("V:"));

  // Valor da Velocidade
  display.setTextSize(2);
  display.setCursor(40, 15);
  display.print(velocidade);
  display.setTextSize(1);
  display.print(F(" km/h"));

  display.display();

  
  delay(100); // Estabiliza a leitura


  if (mcp2515.readMessage(&read_can_msg) == MCP2515::ERROR_OK) {
    // 1. Cálculo de Intervalo entre Requisições do Scanner
    tempoAtualRX = millis(); 
    if (tempoUltimoRX > 0) {
      intervaloEntreReq = tempoAtualRX - tempoUltimoRX;
    }
    tempoUltimoRX = tempoAtualRX;

    // Marca o início do processamento para a latência
    unsigned long inicioProcessamento = micros();
    
    unsigned char p_id = read_can_msg.data[2];
    bool responder = false;

    // Limpa e configura resposta padrão
    memset(write_can_msg.data, 0xAA, 8);
    write_can_msg.can_id  = 0x7E8;
    write_can_msg.can_dlc = 8;
    write_can_msg.data[1] = 0x41; 

    switch (p_id) {
      case 0x00: // Handshake
        write_can_msg.data[0] = 0x06;
        write_can_msg.data[2] = 0x00;
        write_can_msg.data[3] = 0x1A; // Suporta 0D, 0C, 0B
        write_can_msg.data[4] = 0x70; // Suporta 10, 11
        responder = true;
        break;

      case 0x0D: // Velocidade
        write_can_msg.data[0] = 0x03;
        write_can_msg.data[2] = 0x0D;
        write_can_msg.data[3] = (byte)map(analogRead(A0), 0, 1023, 0, 100);
        responder = true;
        break;

      case 0x0C: // RPM
        {
          int rpm = random(800, 3000) * 4;
          write_can_msg.data[0] = 0x04;
          write_can_msg.data[2] = 0x0C;
          write_can_msg.data[3] = highByte(rpm);
          write_can_msg.data[4] = lowByte(rpm);
          responder = true;
        }
        break;

      case 0x0B: // MAP
        write_can_msg.data[0] = 0x03;
        write_can_msg.data[2] = 0x0B;
        write_can_msg.data[3] = (byte)random(30, 100);
        responder = true;
        break;

      case 0x10: // MAF
        {
          int maf = random(500, 2000);
          write_can_msg.data[0] = 0x04;
          write_can_msg.data[2] = 0x10;
          write_can_msg.data[3] = highByte(maf);
          write_can_msg.data[4] = lowByte(maf);
          responder = true;
        }
        break;

      case 0x11: // TPS
        write_can_msg.data[0] = 0x03;
        write_can_msg.data[2] = 0x11;
        write_can_msg.data[3] = (byte)random(0, 100);
        responder = true;
        break;
    }

    if (responder) {
      if (mcp2515.sendMessage(&write_can_msg) == MCP2515::ERROR_OK) {
        latenciaResposta = micros() - inicioProcessamento;
        
        // Log de Telemetria
        Serial.print(F("PID: 0x"));
        if (p_id < 0x10) Serial.print("0");
        Serial.print(p_id, HEX);
        
        Serial.print(F(" | Int. Req: "));
        Serial.print(intervaloEntreReq);
        Serial.print(F(" ms | Lat. Resp: "));
        Serial.print(latenciaResposta);
        Serial.println(F(" us"));
      }
    }
  }
 
}

void imprimirFrame(const char* direcao, const struct can_frame* frame) {
  Serial.print(direcao); // "RX" ou "TX"
  Serial.print(F(" | ID: 0x"));
  Serial.print(frame->can_id, HEX);
  Serial.print(F(" | DLC: "));
  Serial.print(frame->can_dlc);
  Serial.print(F(" | Dados: "));
  for (int i = 0; i < frame->can_dlc; i++) {
    if (frame->data[i] < 0x10) Serial.print("0"); // Padding zero
    Serial.print(frame->data[i], HEX);
    Serial.print(" ");
  }
  Serial.println();
}
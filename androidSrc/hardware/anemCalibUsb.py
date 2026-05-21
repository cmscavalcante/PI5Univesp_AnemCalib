from usb4a import usb
from usbserial4a import serial4a
import threading
import time
from kivy.clock import Clock

class AnemCalibUsb:
    def __init__(self):
        self._serial_port = None
        self._is_connected = False
        self._read_thread = None
        self._data_callback = None
        self._stop_event = threading.Event()

    def set_data_callback(self, callback):
        self._data_callback = callback

    def is_connected(self):
        return self._is_connected

    def _read_loop(self):
        print("Iniciando loop de leitura serial otimizado...")
        buffer = ""
        while not self._stop_event.is_set() and self._serial_port:
            try:
                if self._serial_port.is_open:
                    # Lê o máximo de bytes disponíveis de uma vez
                    waiting = self._serial_port.in_waiting
                    if waiting > 0:
                        chunk = self._serial_port.read(waiting).decode('utf-8', errors='ignore')
                        buffer += chunk
                        # Processa todas as linhas completas no buffer
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if line and self._data_callback:
                                self._data_callback(line)
                    time.sleep(0.005)
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Erro na leitura serial: {e}")
                if self._data_callback:
                    self._data_callback("DISCONNECTED")
                break
        self._is_connected = False

    def connect(self):
        # Se já estiver conectado e a porta estiver aberta, não faz nada
        if self._is_connected and self._serial_port and self._serial_port.is_open:
            return True
        try:
            # Força uma atualização da lista de dispositivos do Android
            device_list = usb.get_usb_device_list()
            if not device_list:
                # Se não há dispositivos, garante que o estado interno reflita isso
                self._is_connected = False
                return False
            # No Android, o dispositivo pode mudar de nome/ID ao ser reconectado
            device = device_list[0]
            # Se a porta serial existe mas o dispositivo mudou ou desconectou
            if self._serial_port and not self._serial_port.is_open:
                self._serial_port = None
            # Verifica permissão e tenta abrir
            if usb.has_usb_permission(device):
                return self._open_serial(device)
            else:
                # Solicita permissão novamente se necessário (caso o ID tenha mudado)
                usb.request_usb_permission(device)
                return True
        except Exception as e:
            print(f"Erro ao tentar reconectar USB: {e}")
            self._is_connected = False
            return False

    def _open_serial(self, device):
        try:
            print(f"Abrindo porta serial para {device.getDeviceName()}...")
            self._serial_port = serial4a.get_serial_port(
                device.getDeviceName(), 
                baudrate=115200, 
                timeout=1
            )
            if not self._serial_port.is_open:
                self._serial_port.open()
            if self._serial_port.is_open:
                self._serial_port.flushInput()
                self._serial_port.flushOutput()
                self._is_connected = True
                self._stop_event.clear()
                self._read_thread = threading.Thread(target=self._read_loop)
                self._read_thread.daemon = True
                self._read_thread.start()
                print("Porta serial aberta e thread de leitura iniciada.")
                return True
            print("Falha ao abrir a porta serial.")
            return False
        except Exception as e:
            print(f"Erro ao abrir serial: {e}")
            return False

    def disconnect(self):
        self._stop_event.set()
        self._is_connected = False
        if self._serial_port:
            try:
                self._serial_port.close()
            except:
                pass
        print("Hardware USB desconectado.")
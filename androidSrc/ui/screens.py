from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.popup import Popup
import datetime
from kivy.properties import (
    StringProperty,
    BooleanProperty,
    ListProperty
)

class ErrorPopup(Popup):
    def __init__(self, retry_callback, **kwargs):
        super().__init__(**kwargs)
        self.retry_callback = retry_callback

    def retry(self):
        self.dismiss()
        self.retry_callback()

    def exit_app(self):
        App.get_running_app().stop()

class MainScreen(Screen):
    # Propriedades para o Veículo (OBD-II)
    obd_speed = StringProperty("0.0")
    obd_tps = StringProperty("0.0")
    obd_maf = StringProperty("0.00")
    obd_map = StringProperty("0.0")
    obd_rpm = StringProperty("0")

    # Propriedades para o Tablet
    utc_time = StringProperty("00:00:00.00")
    terminal_text = StringProperty("")

    # Propriedades para o Dispositivo (ESP32-S3) - Iniciam em branco
    esp_speed = StringProperty("")
    esp_accel_x = StringProperty("")
    esp_accel_y = StringProperty("")
    esp_accel_z = StringProperty("")
    esp_rpm = StringProperty("")
    esp_millis = StringProperty("")
    esp_sats = StringProperty("")
    esp_g = StringProperty("")

    is_connected = BooleanProperty(False)
    test_running = BooleanProperty(False)

    obd_status_color = ListProperty([1, 0.2, 0.5, 1])

    usb_connected = BooleanProperty(False)
    obd_connected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = None
        self.error_popup = None
        # Inicia o relógio UTC
        Clock.schedule_interval(self.update_utc_time, 0.05)
        # Agenda a conexão automática para o próximo frame
        Clock.schedule_once(self.auto_connect, 0.5)

    def auto_connect(self, dt):
        self.app = App.get_running_app()
        self.update_terminal("Iniciando conexão automática...", type="system")
        Clock.schedule_interval(
            self.check_usb_status,
            1.0
        )

    def set_obd_connected(self):
        self.obd_connected = True
        self.obd_status_color = [0, 1, 0, 1]

    def set_obd_disconnected(self):
        self.obd_connected = False
        self.obd_status_color = [1, 0.2, 0.5, 1]

    def set_usb_connected(self):
        self.usb_connected = True

    def set_usb_disconnected(self):
        self.usb_connected = False

    def check_usb_status(self, dt):
        if self.app.usb_manager.is_connected():
            self.is_connected = True
            self.update_terminal("USB Conectado e Ativo!", type="system")
            return False # Para o polling
        
        # Tenta abrir se a permissão já foi dada
        from usb4a import usb
        device_list = usb.get_usb_device_list()
        if device_list and usb.has_usb_permission(device_list[0]):
            if self.app.usb_manager._open_serial(device_list[0]):
                self.is_connected = True
                self.update_terminal("Conexão estabelecida!", type="system")
                return False
        return True

    def show_error_popup(self):
        if not self.error_popup:
            self.error_popup = ErrorPopup(retry_callback=self.auto_connect)
        self.error_popup.open()

    def update_utc_time(self, dt):
        now = datetime.datetime.utcnow()
        self.utc_time = now.strftime("%H:%M:%S.%f")[:-4]

    def update_terminal(self, message, type="res"):
        Clock.schedule_once(lambda dt: self._append_text(message, type))

    def _append_text(self, message, type):
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        if type == "system":
            color = "00FFFF" # Ciano para mensagens internas
        elif type == "error":
            color = "FF0000" # Vermelho para erros
        else:
            color = "00FF00" # Verde para RES:   
        new_line = f"[{timestamp}] [color={color}]{message}[/color]"
        lines = self.terminal_text.split('\n')
        if len(lines) > 50:
            self.terminal_text = '\n'.join(lines[-50:])
        if self.terminal_text == "":
            self.terminal_text = new_line
        else:
            self.terminal_text += f"\n{new_line}"

    def set_esp_error(self):
        self.esp_speed = "#err"
        self.esp_accel_x = "#err"
        self.esp_accel_y = "#err"
        self.esp_accel_z = "#err"
        self.esp_rpm = "#err"
        self.esp_millis = "#err"
        self.esp_sats = "#err"
        self.esp_g = "#err"
        self.update_terminal("ERRO: Conexão com dispositivo perdida!", type="error")

    def update_esp_data(self, data_dict):
        # millis, freqHz, rpm, vGps, accelX, accelY, accelZ, gpsGlocal, sats
        self.esp_millis = data_dict.get('millis', '0')
        self.esp_rpm = data_dict.get('rpm', '0')
        self.esp_speed = data_dict.get('vGps', '0.0')
        self.esp_accel_x = data_dict.get('accelX', '0.00')
        self.esp_accel_y = data_dict.get('accelY', '0.00')
        self.esp_accel_z = data_dict.get('accelZ', '0.00')
        self.esp_sats = data_dict.get('sats', '0')
        # Exibe o dado gpsGlocal vindo do dispositivo (estável)
        self.esp_g = data_dict.get('gpsGlocal', '0.00')

    def update_obd_data(self, data_dict):
        self.obd_speed = data_dict.get('speed', '0.0')
        self.obd_rpm = data_dict.get('rpm', '0')
        self.obd_tps = data_dict.get('tps', '0.0')
        self.obd_maf = data_dict.get('maf', '0.00')
        self.obd_map = data_dict.get('map', '0.0')

    def start_test(self):
        app = App.get_running_app()
        if not self.usb_connected:
            self.update_terminal(
                "USB não conectado",
                type="error"
            )
            return
        if not self.obd_connected:
            self.update_terminal(
                "OBD-II não conectado",
                type="error"
            )
            return
        app.start_test()
        self.update_terminal(
            "Teste iniciado",
            type="system"
        )


    def stop_test(self):
        app = App.get_running_app()
        app.stop_test()
        self.update_terminal(
            "Teste finalizado",
            type="system"
        )
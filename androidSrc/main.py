import time
print("BUILD:", time.time())
import os
os.environ["KIVY_NO_FILELOG"] = "1"
os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ["KIVY_ORIENTATION"] = "Landscape"

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.clock import Clock
from kivy.utils import platform

from ui.screens import MainScreen
from hardware.anemCalibUsb import AnemCalibUsb
from hardware.odb_manager import OBDManager
from core.logger import DataLogger


class AnemCalibApp(App):
    def build(self):
        self.title = "AnemCalib - Telemetria"

        # Inicializa hardware e logger
        self.usb_manager = AnemCalibUsb()
        self.obd_manager = OBDManager()
        self.logger = DataLogger()

        # Watchdog USB
        self.last_usb_data_time = 0
        self.usb_watchdog_active = False

        # Callbacks
        self.usb_manager.set_data_callback(self.on_usb_data)
        self.obd_manager.set_data_callback(self.on_obd_data)

        # UI
        self.sm = ScreenManager()
        self.main_screen = MainScreen(name="main")
        self.sm.add_widget(self.main_screen)

        # Watchdog
        Clock.schedule_interval(self.check_usb_watchdog, 1.0)

        # Inicialização das conexões após UI pronta
        Clock.schedule_once(self.init_connections, 1.0)

        self._pending_obd_data = None

        self.latest_obd_data = {}

        #timestamp monotônico para o log
        self.app_start_perf = time.perf_counter()

        #monitoramento conexões
        self.usb_ready = False
        self.obd_ready = False

        return self.sm

    def init_connections(self, dt):
        # Inicializa USB
        self.usb_manager.connect()

        # Inicializa OBD após permissões
        if platform == "android":
            from android.permissions import request_permissions, Permission
            def permission_callback(permissions, grants):
                print("Permissões:", list(zip(permissions, grants)))

                granted = dict(zip(permissions, grants))

                connect_ok = granted.get(
                    Permission.BLUETOOTH_CONNECT,
                    False
                )
                scan_ok = granted.get(
                    Permission.BLUETOOTH_SCAN,
                    False
                )
                location_ok = granted.get(
                    Permission.ACCESS_FINE_LOCATION,
                    False
                )
                if connect_ok and scan_ok and location_ok:
                    print("Permissões Bluetooth concedidas")
                    Clock.schedule_once(
                        lambda dt: self.obd_manager.connect(),
                        1.0
                    )
                else:
                    print("Permissões Bluetooth incompletas")
            request_permissions(
                [
                    Permission.BLUETOOTH_CONNECT,
                    Permission.BLUETOOTH_SCAN,
                    Permission.ACCESS_FINE_LOCATION
                ],
                permission_callback
            )
        else:
            self.obd_manager.connect()

    def check_usb_watchdog(self, dt):
        import time
        current_time = time.time()
        # USB conectado mas sem dados
        if self.usb_manager.is_connected():
            if (
                self.last_usb_data_time > 0 and
                (current_time - self.last_usb_data_time > 2.0)
            ):
                if not self.usb_watchdog_active:
                    self.usb_watchdog_active = True

                    if hasattr(self, "main_screen") and self.main_screen:
                        self.main_screen.set_esp_error()
            else:
                # Dados voltaram
                if self.usb_watchdog_active:
                    self.usb_watchdog_active = False

                    if hasattr(self, "main_screen") and self.main_screen:
                        self.main_screen.update_terminal(
                            "Conectado novamente",
                            type="system"
                        )
        else:
            # USB desconectado
            if not self.usb_watchdog_active:
                self.usb_watchdog_active = True

                if hasattr(self, "main_screen") and self.main_screen:
                    self.main_screen.set_esp_error()

            # tenta reconectar
            self.usb_manager.connect()

    def on_usb_data(self, data):
        import time
        import datetime
        if not self.usb_ready:
            self.usb_ready = True

            self.main_screen.set_usb_connected(True)

            self.main_screen.update_terminal(
                "ESP32 conectado",
                type="system"
            )
        self.last_usb_data_time = time.time()
        if hasattr(self, "main_screen") and self.main_screen:
            # desconexão
            if data == "DISCONNECTED":
                Clock.schedule_once(
                    lambda dt: self.main_screen.set_esp_error()
                )
                return
            clean_data = data.strip()
            # terminal
            if clean_data.startswith("RES:"):
                self.main_screen.update_terminal(
                    clean_data
                )
                return
            # CSV do ESP
            if "," in clean_data:
                try:
                    parts = clean_data.split(",")
                    if len(parts) >= 9:
                        data_dict = {
                            "millis": parts[0],
                            "freqHz": parts[1],
                            "rpm": parts[2],
                            "vGps": parts[3],
                            "accelX": parts[4],
                            "accelY": parts[5],
                            "accelZ": parts[6],
                            "gpsGlocal": parts[7],
                            "sats": parts[8]
                        }
                        # Atualiza UI
                        Clock.schedule_once(
                            lambda dt: self.main_screen.update_esp_data(
                                data_dict
                            )
                        )
                        # =========================
                        # LOGGER SINCRONIZADO
                        # =========================
                        if self.logger.is_logging:
                            # tempo monotônico global
                            t_app = (
                                time.perf_counter()
                                - self.app_start_perf
                            )
                            # horário humano
                            pc_time = datetime.datetime.now().strftime(
                                "%H:%M:%S.%f"
                            )[:-3]
                            obd_speed = ""
                            if (
                                isinstance(
                                    self.latest_obd_data,
                                    dict
                                )
                            ):
                                obd_speed = (
                                    self.latest_obd_data.get(
                                        "speed",
                                        ""
                                    )
                                )
                            row = [
                                pc_time,
                                f"{t_app:.3f}",
                                # ESP
                                parts[0],  # millis
                                parts[1],  # freqHz
                                parts[2],  # rpm
                                parts[3],  # vGps
                                parts[4],  # accelX
                                parts[5],  # accelY
                                parts[6],  # accelZ
                                parts[7],  # gpsGlocal
                                parts[8],  # sats
                                # OBD
                                obd_speed
                            ]
                            self.logger.log_data(row)
                except Exception as e:
                    print(
                        f"Erro no parse de dados CSV: {e}"
                    )

    def on_obd_data(self, data):
        self.latest_obd_data = data
        if hasattr(self, "main_screen") and self.main_screen:
            if data == "DISCONNECTED":
                self.main_screen.update_terminal(
                    "ERRO: Conexão OBD-II perdida!",
                    type="error"
                )
                return
            self._pending_obd_data = data
            Clock.unschedule(self._update_obd_ui)
            Clock.schedule_once(self._update_obd_ui, 0)
    
    def start_test(self):
        headers = [
            "pc_time",
            "t_app",
            "esp_millis",
            "freqHz",
            "esp_rpm",
            "vGps",
            "accelX",
            "accelY",
            "accelZ",
            "gpsGlocal",
            "sats",
            "obd_speed"
        ]
        self.logger.start(headers)

    def stop_test(self):
        self.logger.stop()

    def on_stop(self):
        # encerra tudo ao sair
        self.usb_manager.disconnect()
        if hasattr(self, "obd_manager"):
            self.obd_manager.disconnect()
        self.logger.stop()

    def _update_obd_ui(self, dt):
        if self._pending_obd_data:
            self.main_screen.update_obd_data(
                self._pending_obd_data
            )

if __name__ == "__main__":
    AnemCalibApp().run()
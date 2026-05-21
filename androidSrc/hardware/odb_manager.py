import threading
import time

from jnius import autoclass

BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
UUID = autoclass("java.util.UUID")

class OBDManager:
    SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

    def __init__(self):
        self.socket = None
        self.input_stream = None
        self.output_stream = None
        self._is_connected = False
        self._data_callback = None
        self._stop_event = threading.Event()
        self._read_thread = None
        self.pids = {
            "speed": "010D"
        }

    def set_data_callback(self, callback):
        self._data_callback = callback

    def is_connected(self):
        return self._is_connected

    def connect(self):
        if self._is_connected:
            return True
        threading.Thread(
            target=self._async_connect,
            daemon=True
        ).start()
        return True

    def _async_connect(self):
        try:
            print("Iniciando conexão Bluetooth OBD...")
            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                print("Bluetooth indisponível")
                return
            if not adapter.isEnabled():
                print("Bluetooth desligado")
                return
            bonded_devices = adapter.getBondedDevices().toArray()
            elm_device = None
            for device in bonded_devices:
                name = device.getName()
                print(f"Dispositivo pareado: {name}")
                if name and (
                    "OBD" in name.upper()
                    or "ELM" in name.upper()
                    or "V-LINK" in name.upper()
                ):
                    elm_device = device
                    break
            if elm_device is None:
                print("ELM327 não encontrado")
                return
            if adapter.isDiscovering():
                adapter.cancelDiscovery()
                while adapter.isDiscovering():
                    time.sleep(0.05)
            print(f"Conectando em: {elm_device.getName()}")
            uuid = UUID.fromString(self.SPP_UUID)
            self.socket = elm_device.createRfcommSocketToServiceRecord(
                uuid
            )
            self.socket.connect()
            self.input_stream = self.socket.getInputStream()
            self.output_stream = self.socket.getOutputStream()
            print("Bluetooth conectado")
            ok = self._initialize_elm()
            if not ok:
                print("Falha inicialização ELM327")
                if self._data_callback:
                    self._data_callback("INIT_FAIL")
                self.disconnect()
                return
            self._is_connected = True
            if self._data_callback:
                self._data_callback("INIT_OK")
            self._stop_event.clear()
            self._read_thread = threading.Thread(
                target=self._read_loop,
                daemon=True
            )
            self._read_thread.start()
        except Exception as e:
            print(f"Erro conexão OBD: {e}")
            self.disconnect()

    def _initialize_elm(self):
        commands = [
            ("ATZ", 3.0),
            ("ATE0", 1.0),
            ("ATL0", 1.0),
            ("ATS0", 1.0),
            ("ATAT1", 1.0),
            ("ATCAF1", 1.0),
            ("ATSP6", 1.0)
        ]
        for cmd, timeout in commands:
            response = self._send_command(
                cmd,
                timeout
            )
            print(f"{cmd} -> {response}")
            if not response:
                return False
            if "ERROR" in response.upper():
                return False
            if cmd == "ATZ":
                time.sleep(1.5)
            else:
                time.sleep(0.2)
        return True

    def _send_command(self, command, timeout=0.30):
        try:
            if not self.output_stream:
                return ""
            cmd = command + "\r"
            self.output_stream.write(
                cmd.encode("utf-8")
            )
            self.output_stream.flush()
            buffer = ""
            start = time.perf_counter()
            while (time.perf_counter() - start) < timeout:
                b = self.input_stream.read()
                if b == -1:
                    break
                ch = chr(b)
                buffer += ch
                # resposta COMPLETA do ELM
                if ch == ">":
                   break
            cleaned = (
                buffer
                .replace("\r", "")
                .replace("\n", "")
                .replace(">", "")
                .strip()
            )
            return cleaned
        except Exception as e:
            print(f"Erro comando {command}: {e}")
            return ""
    
    def _parse_response(self, pid, response):
        try:
            if not response:
                return None
            response = response.upper()
            # procura frame válido 41 0D XX
            idx = response.find("410D")
            if "410D" not in response:
                return None
            if idx == -1:
                return None
            frame = response[idx:idx + 6]
            if len(frame) < 6:
                return None
            speed_hex = frame[4:6]
            if len(speed_hex) != 2:
                return None
            value = int(speed_hex, 16)
            return float(value)
        except Exception as e:
            print(f"Erro parse: {e} | response={response}")
            return None
    
    def _read_loop(self):
        print("Iniciando loop OBD...")
        target_period = 0.12
        while (
            not self._stop_event.is_set()
            and self._is_connected
        ):
            loop_start = time.perf_counter()
            response = self._send_command(
                "010D",
                timeout=0.20
            )
            #
            if not response:
                continue
            if response == "NO DATA":
                continue
            timestamp = time.perf_counter()
            print(f"RAW OBD RESPONSE = [{response}]")
            value = self._parse_response(
                "010D",
                response
            )
            if value is not None:
                print(
                    f"OBD speed={value} "
                    f"t={timestamp}"
                )
                if self._data_callback:
                    self._data_callback({
                        "speed": f"{value:.1f}",
                        "timestamp_obd": timestamp
                    })
            elapsed = (
                time.perf_counter() - loop_start
            )
            remaining = target_period - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def disconnect(self):
        self._stop_event.set()
        self._is_connected = False
        try:
            if self.input_stream:
                self.input_stream.close()
        except:
            pass
        try:
            if self.output_stream:
                self.output_stream.close()
        except:
            pass
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        self.socket = None
        self.input_stream = None
        self.output_stream = None
        if self._data_callback:
            self._data_callback("DISCONNECTED")
        print("OBD desconectado")
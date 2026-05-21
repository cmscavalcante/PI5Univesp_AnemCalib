import csv
import threading
import os

from datetime import datetime

class DataLogger:

    def __init__(self):
        self._lock = threading.Lock()
        self._filename = None
        self._file = None
        self._writer = None
        self._is_logging = False

    def _generate_filename(self):
        timestamp = datetime.now().strftime("%d%m%Y-%H%M%S")
        filename = f"Teste_{timestamp}.csv"
        if 'ANDROID_ARGUMENT' in os.environ:
            base_path = "/storage/emulated/0/Documents/AnemCalib"
            os.makedirs(base_path, exist_ok=True)
            return os.path.join(base_path, filename)
        return filename

    def start(self, headers):
        with self._lock:
            if self._is_logging:
                return False
            try:
                # novo arquivo a cada teste
                self._filename = (
                    self._generate_filename()
                )
                self._file = open(
                    self._filename,
                    mode="w",
                    newline="",
                    encoding="utf-8"
                )
                self._writer = csv.writer(
                    self._file
                )
                self._writer.writerow(headers)
                self._file.flush()
                self._is_logging = True
                print(
                    f"Log iniciado: "
                    f"{self._filename}"
                )
                return True
            except Exception as e:
                print(
                    f"Erro ao iniciar log: {e}"
                )
                return False

    def log_data(self, data_row):
        if not self._is_logging:
            return False
        with self._lock:
            try:
                self._writer.writerow(data_row)
                # grava imediatamente
                self._file.flush()
                return True
            except Exception as e:
                print(
                    f"Erro ao gravar dados: {e}"
                )
                return False

    def stop(self):
        with self._lock:
            if not self._is_logging:
                return False
            try:
                if self._file:
                    self._file.flush()
                    self._file.close()
                print(
                    f"Log finalizado: "
                    f"{self._filename}"
                )
            except Exception as e:
                print(
                    f"Erro ao fechar log: {e}"
                )
                return False
            finally:
                self._file = None
                self._writer = None
                self._is_logging = False
            return True

    @property
    def is_logging(self):
        return self._is_logging

    @property
    def current_filename(self):
        return self._filename
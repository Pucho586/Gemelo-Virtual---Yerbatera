"""Replay service: lee un CSV histórico de yerba_history y reproduce el estado.

Cuando el modo es 'replay', el runtime pausa el cálculo matemático del simulador y
en su lugar el ReplayService va escribiendo los valores de cada fila del CSV en
las variables del simulador (zapecado/secado/canchado/cámaras).

Soporta play / pause / seek y velocidad configurable (1x, 5x, 10x, 60x).
"""
from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReplayService:
    """Reproductor de CSV histórico que alimenta el simulador en modo 'replay'."""

    def __init__(self, simulator, data_dir: Path):
        self.simulator = simulator
        self.data_dir = data_dir
        self.lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()  # cuando set → pausado

        # Estado
        self.active: bool = False
        self.file: Optional[str] = None
        self.speed: float = 10.0          # 1x, 5x, 10x, 60x
        self.rows: List[Dict[str, str]] = []
        self.cursor: int = 0              # índice actual

    # ---------- API ----------
    def list_files(self) -> List[Dict[str, Any]]:
        files = []
        if not self.data_dir.exists():
            return files
        for p in sorted(self.data_dir.glob("yerba_history_*.csv"), reverse=True):
            files.append({"name": p.name, "size": p.stat().st_size})
        return files

    def start(self, file: str, speed: float = 10.0, start_row: int = 0) -> Dict[str, Any]:
        with self.lock:
            self.stop_locked()
            path = self.data_dir / file
            if not path.exists():
                raise FileNotFoundError(file)
            with open(path, "r", newline="") as f:
                self.rows = list(csv.DictReader(f))
            if not self.rows:
                raise ValueError("CSV vacío")
            self.file = file
            self.speed = max(0.25, min(120.0, float(speed)))
            self.cursor = max(0, min(len(self.rows) - 1, int(start_row)))
            self.active = True
            self._stop_evt.clear()
            self._pause_evt.clear()
            self._thread = threading.Thread(target=self._loop, name="replay-loop", daemon=True)
            self._thread.start()
            return self.status_locked()

    def stop(self):
        with self.lock:
            self.stop_locked()

    def stop_locked(self):
        self._stop_evt.set()
        self.active = False
        # No bloqueamos esperando al thread (es daemon)

    def pause(self, paused: bool):
        with self.lock:
            if paused:
                self._pause_evt.set()
            else:
                self._pause_evt.clear()

    def seek(self, row: int):
        with self.lock:
            if not self.rows:
                return
            self.cursor = max(0, min(len(self.rows) - 1, int(row)))
            # Aplicar inmediatamente la fila seleccionada
            self._apply_row(self.rows[self.cursor])

    def set_speed(self, speed: float):
        with self.lock:
            self.speed = max(0.25, min(120.0, float(speed)))

    def status(self) -> Dict[str, Any]:
        with self.lock:
            return self.status_locked()

    def status_locked(self) -> Dict[str, Any]:
        total = len(self.rows)
        return {
            "active": self.active,
            "paused": self._pause_evt.is_set(),
            "file": self.file,
            "speed": self.speed,
            "cursor": self.cursor,
            "total": total,
            "progress": (self.cursor / total) if total else 0.0,
            "ts_at_cursor": (self.rows[self.cursor].get("ts") if 0 <= self.cursor < total else None),
        }

    # ---------- Loop ----------
    def _loop(self):
        """Avanza una fila a la velocidad configurada. Período base = 1s real entre filas
        (las filas se graban a 5-10s sim, pero al replay las usamos como pasos discretos)."""
        while not self._stop_evt.is_set():
            if self._pause_evt.is_set():
                time.sleep(0.2)
                continue
            with self.lock:
                if self.cursor >= len(self.rows):
                    self.active = False
                    return
                row = self.rows[self.cursor]
                self.cursor += 1
            try:
                self._apply_row(row)
            except Exception as e:
                logger.debug(f"replay apply: {e}")
            # Sleep proporcional inverso a la velocidad
            # speed 1x = 1.0s, 10x = 0.1s, 60x = ~0.016s
            time.sleep(max(0.02, 1.0 / max(self.speed, 0.25)))

    def _apply_row(self, row: Dict[str, str]):
        """Aplica los valores del CSV al simulador (sin recalcular).
        Columnas reales del persistence: zap_temperatura, sec_temperatura, sec_humedad,
        can_velocidad_molino, cam{1..N}_temperatura, cam{1..N}_humedad, cam{1..N}_co2."""
        def fnum(key, default=0.0):
            try:
                return float(row.get(key, default) or default)
            except (ValueError, TypeError):
                return default

        sim = self.simulator
        with sim.lock:
            sim.zapecado.temperatura = fnum("zap_temperatura", sim.zapecado.temperatura)
            sim.secado.temperatura = fnum("sec_temperatura", sim.secado.temperatura)
            sim.secado.humedad = fnum("sec_humedad", sim.secado.humedad)
            sim.canchado.velocidad_molino = fnum("can_velocidad_molino", sim.canchado.velocidad_molino)
            sim.canchado.tamano_particula = fnum("can_tamano_particula", sim.canchado.tamano_particula)
            # Cámaras 1-indexed en el CSV
            for i, cam in enumerate(sim.camaras):
                prefix = f"cam{i+1}_"
                cam.temperatura = fnum(prefix + "temperatura", cam.temperatura)
                cam.humedad = fnum(prefix + "humedad", cam.humedad)
                cam.co2 = fnum(prefix + "co2", cam.co2)
                cam.carga_kg = fnum(prefix + "carga_kg", cam.carga_kg)

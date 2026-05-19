"""Persistencia automática a CSV/Excel del estado del gemelo."""
import asyncio
import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


def _flatten(state: Dict[str, Any]) -> Dict[str, Any]:
    """Aplana el snapshot del simulador en una fila para CSV/Excel."""
    out = {
        "ts": state["ts"],
        "ambient_temp": state["ambient"]["temp"],
        "ambient_humidity": state["ambient"]["humidity"],
        "ambient_city": state["ambient"].get("city", ""),
        "zap_temperatura": state["zapecado"]["temperatura"],
        "zap_velocidad_tambor": state["zapecado"]["velocidad_tambor"],
        "zap_velocidad_chip": state["zapecado"]["velocidad_chip"],
        "zap_alimentacion": int(state["zapecado"]["estado_alimentacion"]),
        "sec_temperatura": state["secado"]["temperatura"],
        "sec_humedad": state["secado"]["humedad"],
        "sec_velocidad_aire": state["secado"]["velocidad_aire"],
        "sec_estado": int(state["secado"]["estado"]),
        "can_velocidad_molino": state["canchado"]["velocidad_molino"],
        "can_tamano_particula": state["canchado"]["tamano_particula"],
        "can_estado": int(state["canchado"]["estado"]),
    }
    for cam in state["camaras"]:
        i = cam["id"] + 1
        out[f"cam{i}_temperatura"] = cam["temperatura"]
        out[f"cam{i}_humedad"] = cam["humedad"]
        out[f"cam{i}_co2"] = cam["co2"]
        out[f"cam{i}_carga_kg"] = cam["carga_kg"]
        out[f"cam{i}_dias"] = cam["tiempo_maduracion"]
        out[f"cam{i}_ventilador"] = int(cam["ventilador"])
    return out


class PersistenceService:
    """Escribe el estado del simulador a CSV cada `interval` segundos."""

    def __init__(self, simulator, data_dir: str | Path, interval: int = 5, enabled: bool = True):
        self.simulator = simulator
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.interval = max(1, int(interval))
        self.enabled = enabled
        self._task: asyncio.Task | None = None
        self.last_write: str | None = None
        self.rows_written = 0

    @property
    def current_filename(self) -> Path:
        """Un archivo por día."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.data_dir / f"yerba_history_{day}.csv"

    def _append_row(self, row: Dict[str, Any]):
        f = self.current_filename
        is_new = not f.exists()
        with open(f, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    async def _loop(self):
        while True:
            try:
                if self.enabled:
                    state = self.simulator.get_state()
                    row = _flatten(state)
                    self._append_row(row)
                    self.last_write = row["ts"]
                    self.rows_written += 1
            except Exception as e:
                logger.warning(f"Persistence error: {e}")
            await asyncio.sleep(self.interval)

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        loop = loop or asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())

    def list_files(self):
        files = sorted(self.data_dir.glob("yerba_history_*.csv"))
        return [
            {
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
            for f in files
        ]

    def get_file_path(self, name: str) -> Path | None:
        p = self.data_dir / name
        if p.exists() and p.parent == self.data_dir:
            return p
        return None

    def build_excel(self, name: str | None = None) -> Path:
        """Convierte un CSV diario (o todos) en un xlsx."""
        target_csv = self.get_file_path(name) if name else None
        out_name = (target_csv.stem if target_csv else "yerba_history_all") + ".xlsx"
        out_path = self.data_dir / out_name
        if target_csv:
            df = pd.read_csv(target_csv)
        else:
            files = sorted(self.data_dir.glob("yerba_history_*.csv"))
            if not files:
                raise FileNotFoundError("No hay CSV todavía")
            df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        df.to_excel(out_path, index=False)
        return out_path

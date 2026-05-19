"""Gestión de lotes (batches) con persistencia en MongoDB."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BatchService:
    def __init__(self, db):
        self.db = db

    async def ensure_indexes(self):
        await self.db.batches.create_index("id", unique=True)
        await self.db.batches.create_index("started_at")

    async def list_batches(self, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.db.batches.find({}, {"_id": 0}).sort("started_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return await self.db.batches.find_one({"id": batch_id}, {"_id": 0})

    async def create_batch(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        bid = data.get("id") or f"L-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        doc = {
            "id": bid,
            "started_at": now_iso(),
            "finished_at": None,
            "status": "running",
            "operario": data.get("operario", username),
            "receta_id": data.get("receta_id"),
            "receta_nombre": data.get("receta_nombre"),
            "kg_entrada": float(data.get("kg_entrada", 0)),
            "kg_salida": None,
            "merma_pct": None,
            "observaciones": data.get("observaciones", ""),
            "snapshots": [],  # se llenan al cerrar
            "created_by": username,
        }
        await self.db.batches.insert_one(doc)
        doc.pop("_id", None)
        return doc

    async def close_batch(self, batch_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        kg_salida = float(data.get("kg_salida", 0))
        existing = await self.get_batch(batch_id)
        if not existing:
            return None
        kg_entrada = existing.get("kg_entrada", 0)
        merma = ((kg_entrada - kg_salida) / kg_entrada * 100.0) if kg_entrada > 0 else None
        update = {
            "finished_at": now_iso(),
            "status": "finished",
            "kg_salida": kg_salida,
            "merma_pct": round(merma, 2) if merma is not None else None,
            "observaciones": data.get("observaciones", existing.get("observaciones", "")),
        }
        await self.db.batches.update_one({"id": batch_id}, {"$set": update})
        return await self.get_batch(batch_id)

    async def cancel_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        await self.db.batches.update_one({"id": batch_id}, {"$set": {"status": "cancelled", "finished_at": now_iso()}})
        return await self.get_batch(batch_id)

    async def get_active(self) -> Optional[Dict[str, Any]]:
        return await self.db.batches.find_one({"status": "running"}, {"_id": 0})

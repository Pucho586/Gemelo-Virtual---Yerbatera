"""Audit trail: registra todas las acciones modificadoras de usuarios."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditService:
    def __init__(self, db):
        self.db = db

    async def ensure_indexes(self):
        await self.db.audit_log.create_index([("ts", -1)])
        await self.db.audit_log.create_index("username")

    async def log(self, username: str, action: str, details: Dict[str, Any] | None = None,
                  ip: Optional[str] = None):
        try:
            await self.db.audit_log.insert_one({
                "ts": now_iso(),
                "username": username,
                "action": action,
                "details": details or {},
                "ip": ip,
            })
        except Exception:
            # No bloquear flujos por fallo de logging
            pass

    async def list_recent(self, limit: int = 200, username: Optional[str] = None) -> List[Dict[str, Any]]:
        q = {}
        if username:
            q["username"] = username
        cursor = self.db.audit_log.find(q, {"_id": 0}).sort("ts", -1).limit(limit)
        return await cursor.to_list(length=limit)

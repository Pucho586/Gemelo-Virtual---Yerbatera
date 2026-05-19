"""Autenticación local con JWT + bcrypt + roles (admin / operario)."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request

JWT_ALGORITHM = "HS256"
ACCESS_TTL = timedelta(hours=8)  # turno completo
REFRESH_TTL = timedelta(days=14)


def _secret() -> str:
    s = os.environ.get("JWT_SECRET", "")
    if not s:
        # Genera y persiste un secret local (solo para primer arranque)
        s = secrets.token_hex(32)
        os.environ["JWT_SECRET"] = s
    return s


# --------- Password ---------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# --------- JWT ---------
def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id, "username": username, "role": role,
        "exp": datetime.now(timezone.utc) + ACCESS_TTL, "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + REFRESH_TTL, "type": "refresh",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])


# --------- Auth helpers para FastAPI ---------
async def get_current_user(request: Request, db) -> Dict[str, Any]:
    # 1) Authorization: Bearer
    token = None
    auth_h = request.headers.get("Authorization", "")
    if auth_h.startswith("Bearer "):
        token = auth_h[7:]
    # 2) cookie
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def require_role(role: str):
    """Dependency factory: exige un rol específico."""
    async def dep(user=None):
        if user is None:
            raise HTTPException(401, "No autenticado")
        if user.get("role") != role and user.get("role") != "admin":
            raise HTTPException(403, f"Requiere rol {role}")
        return user
    return dep


# --------- Seeding ---------
DEFAULT_USERS = [
    {"username": "admin", "password": "admin", "role": "admin", "display": "Administrador"},
    {"username": "operario", "password": "operario", "role": "operator", "display": "Operario"},
]


async def seed_users(db):
    """Crea admin/operario si no existen (idempotente)."""
    import uuid as _uuid
    await db.users.create_index("username", unique=True)
    for u in DEFAULT_USERS:
        existing = await db.users.find_one({"username": u["username"]})
        if not existing:
            await db.users.insert_one({
                "id": str(_uuid.uuid4()),
                "username": u["username"],
                "password_hash": hash_password(u["password"]),
                "role": u["role"],
                "display": u["display"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })


# --------- Recovery ---------
def get_recovery_code() -> str:
    """Código maestro guardado en .env para resetear contraseñas sin email."""
    return os.environ.get("ADMIN_RECOVERY_CODE", "yerbatera-recovery-2026")

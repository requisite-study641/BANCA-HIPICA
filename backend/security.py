"""
Autenticación por token Bearer y hashing de contraseñas.

Esquema: SHA-256 con salt aleatorio por usuario, guardado como ``salt$digest``.
El token de sesión se emite con ``secrets.token_urlsafe`` y se persiste en la
tabla ``auth_tokens``.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import ROLE_ADMIN, AuthToken, User, get_db


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Genera ``salt$sha256(salt:password)``."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Compara de forma constante en tiempo la contraseña contra el hash."""
    try:
        salt, digest = stored.split("$", 1)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(candidate, digest)


def create_token(db: Session, user: User) -> str:
    """Crea una sesión persistente y devuelve el token Bearer."""
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token=token, user_id=user.id))
    db.commit()
    return token


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Dependencia: usuario autenticado (Header: ``Authorization: Bearer <token>``)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta el token de autenticación.")
    token = authorization.split(" ", 1)[1].strip()
    record = db.query(AuthToken).filter(AuthToken.token == token).first()
    if record is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependencia: únicamente el administrador pasa esta restricción."""
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Acceso restringido al administrador.")
    return user
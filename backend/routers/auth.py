"""Endpoints de autenticación: registro, inicio de sesión, perfil y cierre de sesión."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import ROLE_USER, AuthToken, User, get_db
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Crea una cuenta con balance 0 e inicia sesión automáticamente."""
    username = payload.username.strip()
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="La contraseña debe tener 4 caracteres o más.")
    exists = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe.")

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        balance=0.0,
        role=ROLE_USER,  # El registro público siempre crea cuentas 'user'.
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(db, user)
    return AuthResponse(token=token, user=UserOut(**user.to_dict()))


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Valida credenciales y devuelve un token Bearer."""
    user = (
        db.query(User)
        .filter(func.lower(User.username) == payload.username.strip().lower())
        .first()
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    token = create_token(db, user)
    return AuthResponse(token=token, user=UserOut(**user.to_dict()))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Perfil del usuario autenticado (incluye el balance actualizado)."""
    return UserOut(**user.to_dict())


@router.post("/auth/logout")
def logout(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Invalida el token Bearer actual (cierra sesión en el servidor)."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        db.query(AuthToken).filter(AuthToken.token == token).delete()
        db.commit()
    return {"detail": "Sesión cerrada."}
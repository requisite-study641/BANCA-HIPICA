"""Gestión bancaria, recargas por pago móvil y retiros (usuarios y admin)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import (
    REQ_APPROVED,
    REQ_PAID,
    REQ_PENDING,
    REQ_REJECTED,
    BankInfo,
    TopUpRequest,
    User,
    WithdrawalRequest,
    get_db,
)
from ..schemas import BankInfoUpdate, TopUpCreate, WithdrawCreate
from ..security import get_current_user, require_admin

router = APIRouter(tags=["payments"])

# Los montos se redondean a 2 decimales en toda la capa de pagos.
def _money(value: float) -> float:
    return round(float(value), 2)


# ───────────────────── Datos bancarios del administrador ─────────────────────
@router.get("/bank")
def get_bank(db: Session = Depends(get_db)):
    """Datos bancarios centralizados que el usuario necesita para recargar."""
    info = db.query(BankInfo).order_by(BankInfo.id).first()
    return info.to_dict() if info else None


@router.put("/admin/bank")
def update_bank(
    payload: BankInfoUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Configura (upsert) los datos bancarios/wallet del administrador."""
    info = db.query(BankInfo).order_by(BankInfo.id).first()
    if info is None:
        info = BankInfo()
        db.add(info)
    info.bank_name = payload.bank_name.strip()
    info.phone = payload.phone.strip()
    info.id_number = payload.id_number.strip()
    info.account_type = payload.account_type.strip()
    info.holder_name = payload.holder_name.strip()
    info.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(info)
    return info.to_dict()


# ───────────────────────────── Recargas (usuario) ─────────────────────────────
@router.post("/payments/topup", status_code=201)
def create_topup(
    payload: TopUpCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reporta un pago móvil realizado; queda PENDIENTE hasta que el admin lo apruebe."""
    if _money(payload.amount) <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor que cero.")
    request = TopUpRequest(
        user_id=user.id,
        amount=_money(payload.amount),
        reference=payload.reference.strip(),
        wallet_phone=payload.wallet_phone.strip(),
        status=REQ_PENDING,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request.to_dict()


@router.get("/payments/topups")
def my_topups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Historial de recargas del usuario autenticado."""
    rows = (
        db.query(TopUpRequest)
        .filter(TopUpRequest.user_id == user.id)
        .order_by(TopUpRequest.created_at.desc())
        .all()
    )
    return [r.to_dict() for r in rows]


# ─────────────────────── Admin: reportes y aprobaciones ───────────────────────
def _review_queue(db: Session, model, status: Optional[str]):
    """Lista enriquecida con el username del dueño de la solicitud."""
    query = db.query(model)
    if status:
        query = query.filter(model.status == status.upper())
    rows = query.order_by(model.created_at.desc()).all()
    result = []
    for row in rows:
        data = row.to_dict()
        owner = db.get(User, row.user_id)
        data["username"] = owner.username if owner else f"usuario #{row.user_id}"
        result.append(data)
    return result


@router.get("/admin/topups")
def list_topups(
    status: Optional[str] = Query(default=None, description="PENDING | APPROVED | REJECTED"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Cola de recargas reportadas por los usuarios."""
    return _review_queue(db, TopUpRequest, status)


@router.post("/admin/topups/{request_id}/approve")
def approve_topup(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Aprueba una recarga y ABONA el monto al balance del usuario."""
    request = db.get(TopUpRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud de recarga no encontrada.")
    if request.status != REQ_PENDING:
        raise HTTPException(status_code=409, detail="La solicitud ya fue revisada.")

    owner = db.get(User, request.user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    owner.balance = _money((owner.balance or 0.0) + request.amount)
    request.status = REQ_APPROVED
    request.reviewed_at = datetime.utcnow()
    request.reviewed_by = admin.id
    db.commit()
    db.refresh(request)
    data = request.to_dict()
    data["username"] = owner.username
    data["new_balance"] = owner.balance
    return data


@router.post("/admin/topups/{request_id}/reject")
def reject_topup(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Rechaza una recarga (no modifica el balance)."""
    request = db.get(TopUpRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud de recarga no encontrada.")
    if request.status != REQ_PENDING:
        raise HTTPException(status_code=409, detail="La solicitud ya fue revisada.")
    request.status = REQ_REJECTED
    request.reviewed_at = datetime.utcnow()
    request.reviewed_by = admin.id
    db.commit()
    db.refresh(request)
    return request.to_dict()


@router.get("/admin/withdrawals")
def list_withdrawals(
    status: Optional[str] = Query(default=None, description="PENDING | PAID | REJECTED"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Cola de retiros solicitados por los usuarios."""
    return _review_queue(db, WithdrawalRequest, status)


@router.post("/admin/withdrawals/{request_id}/pay")
def pay_withdrawal(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Marca un retiro como PAGADO (el saldo ya estaba retenido al solicitarlo)."""
    request = db.get(WithdrawalRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud de retiro no encontrada.")
    if request.status != REQ_PENDING:
        raise HTTPException(status_code=409, detail="La solicitud ya fue revisada.")
    request.status = REQ_PAID
    request.reviewed_at = datetime.utcnow()
    request.reviewed_by = admin.id
    db.commit()
    db.refresh(request)
    return request.to_dict()


@router.post("/admin/withdrawals/{request_id}/reject")
def reject_withdrawal(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Rechaza un retiro y REEMBOLSA el monto retenido al balance del usuario."""
    request = db.get(WithdrawalRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud de retiro no encontrada.")
    if request.status != REQ_PENDING:
        raise HTTPException(status_code=409, detail="La solicitud ya fue revisada.")

    owner = db.get(User, request.user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    owner.balance = _money((owner.balance or 0.0) + request.amount)
    request.status = REQ_REJECTED
    request.reviewed_at = datetime.utcnow()
    request.reviewed_by = admin.id
    db.commit()
    db.refresh(request)
    data = request.to_dict()
    data["username"] = owner.username
    data["new_balance"] = owner.balance
    return data
"""Auditoría administrativa: balances, volumen de duelos y comisiones del 5%."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import (
    DUEL_ACTIVE,
    DUEL_OPEN,
    DUEL_RESOLVED,
    REQ_APPROVED,
    REQ_PAID,
    REQ_PENDING,
    TopUpRequest,
    User,
    WithdrawalRequest,
    Duel,
    get_db,
)
from ..security import require_admin

router = APIRouter(tags=["audit"])


def _sum(db: Session, column, *filters) -> float:
    """Suma con COALESCE(..., 0) aplicando los filtros indicados (2 decimales)."""
    value = db.query(func.coalesce(func.sum(column), 0.0)).filter(*filters).scalar() or 0.0
    return round(float(value), 2)


@router.get("/admin/audit")
def audit_summary(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    """
    Auditoría general:
      * balances totales de los usuarios,
      * volumen de duelos y comisiones retenidas (5%),
      * fondos bloqueados en escrow,
      * volúmenes de recargas y retiros.
    """
    total_balance = _sum(db, User.balance)
    users_count = db.query(func.count(User.id)).scalar() or 0

    open_count = db.query(func.count(Duel.id)).filter(Duel.status == DUEL_OPEN).scalar() or 0
    active_count = db.query(func.count(Duel.id)).filter(Duel.status == DUEL_ACTIVE).scalar() or 0
    resolved_count = (
        db.query(func.count(Duel.id)).filter(Duel.status == DUEL_RESOLVED).scalar() or 0
    )

    resolved_volume = _sum(db, Duel.stake * 2, Duel.status == DUEL_RESOLVED)
    commissions = _sum(db, Duel.commission_amount, Duel.status == DUEL_RESOLVED)
    payouts = _sum(db, Duel.payout_amount, Duel.status == DUEL_RESOLVED)
    escrow_open = _sum(db, Duel.stake, Duel.status == DUEL_OPEN)
    escrow_active = _sum(db, Duel.stake * 2, Duel.status == DUEL_ACTIVE)

    topup_approved = _sum(db, TopUpRequest.amount, TopUpRequest.status == REQ_APPROVED)
    topup_pending = _sum(db, TopUpRequest.amount, TopUpRequest.status == REQ_PENDING)
    withdrawals_paid = _sum(db, WithdrawalRequest.amount, WithdrawalRequest.status == REQ_PAID)
    withdrawals_pending = _sum(
        db, WithdrawalRequest.amount, WithdrawalRequest.status == REQ_PENDING
    )

    return {
        "users": {
            "count": int(users_count),
            "total_balance": total_balance,
        },
        "duels": {
            "open": int(open_count),
            "active": int(active_count),
            "resolved": int(resolved_count),
            "resolved_volume": resolved_volume,
            "commissions": commissions,          # 5% de cada pozo resuelto.
            "payouts_to_winners": payouts,       # 95% abonado a ganadores.
            "fee_percentage": 0.05,
        },
        "escrow": {
            "held_open": escrow_open,            # stakes retenidos de duelos abiertos.
            "held_active": escrow_active,        # pozos completos de duelos activos.
            "total_held": round(escrow_open + escrow_active, 2),
        },
        "payments": {
            "topups_approved_volume": topup_approved,
            "topups_pending_volume": topup_pending,
            "withdrawals_paid_volume": withdrawals_paid,
            "withdrawals_pending_volume": withdrawals_pending,
        },
    }


@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    """Padrón de cuentas con balances (auditoría de cuentas)."""
    users = db.query(User).order_by(User.balance.desc()).all()
    return [u.to_dict() for u in users]
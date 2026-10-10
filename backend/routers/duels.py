"""Duelos P2P: creación con escrow, listado, aceptación y resolución administrativa."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import (
    DUEL_ACTIVE,
    DUEL_OPEN,
    DUEL_RESOLVED,
    FEE_PERCENTAGE,
    ROLE_ADMIN,
    RULE_HIGHEST,
    RULE_LOWEST,
    RULE_OFFICIAL,
    RULE_TIE,
    User,
    Duel,
    DuelType,
    RaceEntry,
    get_db,
    get_official_positions,
    official_outcome,
)
from ..schemas import DuelAccept, DuelCreate, ResolveDuel
from ..security import get_current_user, require_admin

router = APIRouter(tags=["duels"])


# ────────────────────────────── Serialización ──────────────────────────────
def _serialize(duel: Duel, db: Session) -> dict:
    data = duel.to_dict()
    duel_type = db.get(DuelType, duel.duel_type_id)
    creator = db.get(User, duel.creator_id)
    acceptor = db.get(User, duel.acceptor_id) if duel.acceptor_id else None
    winner = db.get(User, duel.winner_id) if duel.winner_id else None
    data.update(
        {
            "duel_type_name": duel_type.name if duel_type else "—",
            "logic_rule": duel_type.logic_rule if duel_type else None,
            "creator_username": creator.username if creator else "—",
            "acceptor_username": acceptor.username if acceptor else None,
            "winner_username": winner.username if winner else None,
            "pot": round((duel.stake or 0.0) * 2, 2),
        }
    )
    return data


# ─────────────────────────── Lectura (usuarios) ───────────────────────────
@router.get("/duels/available")
def available_duels(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Duelos abiertos por la comunidad (excluye los propios del usuario)."""
    duels = (
        db.query(Duel)
        .filter(Duel.status == DUEL_OPEN, Duel.creator_id != user.id)
        .order_by(Duel.created_at.desc())
        .all()
    )
    return [_serialize(d, db) for d in duels]


@router.get("/duels/mine")
def my_duels(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Duelos donde el usuario es creador u oponente."""
    duels = (
        db.query(Duel)
        .filter((Duel.creator_id == user.id) | (Duel.acceptor_id == user.id))
        .order_by(Duel.created_at.desc())
        .all()
    )
    return [_serialize(d, db) for d in duels]


@router.get("/duels/{duel_id}")
def get_duel(
    duel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    duel = db.get(Duel, duel_id)
    if duel is None:
        raise HTTPException(status_code=404, detail="Duelo no encontrado.")
    return _serialize(duel, db)

# ────────────────────────────── Crear duelo ──────────────────────────────
@router.post("/duels/create", status_code=201)
def create_duel(
    payload: DuelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Publica un duelo: soporta tipos individuales, MARCAS y MOROCHA (2 vs 2).
    El stake se DESCUENTA del balance del creador y queda en escrow.
    """
    duel_type = db.get(DuelType, payload.duel_type_id)
    if duel_type is None:
        raise HTTPException(status_code=404, detail="Tipo de duelo no encontrado.")

    is_morocha = getattr(duel_type, "is_morocha", False)
    is_matchup = getattr(duel_type, "is_matchup", False)

    # Si es una modalidad INDIVIDUAL (no es MATCHUP ni MOROCHA), asignamos internamente el mismo caballo
    if not is_matchup and not is_morocha:
        payload.horse_opponent = payload.horse_creator

    # 1. Validaciones de duplicidad según el tipo de duelo
    if is_morocha:
        if not (payload.horse_creator_2 and payload.horse_opponent_2):
            raise HTTPException(
                status_code=400,
                detail="Debes seleccionar los 4 caballos para la modalidad MOROCHA."
            )
        
        selected_horses = [
            payload.horse_creator,
            payload.horse_creator_2,
            payload.horse_opponent,
            payload.horse_opponent_2,
        ]
        if len(set(selected_horses)) < 4:
            raise HTTPException(
                status_code=400,
                detail="Los 4 caballos seleccionados para MOROCHA deben ser distintos entre sí."
            )
    elif is_matchup:
        # ÚNICAMENTE exigimos que sean distintos si es un duelo 1vs1 MARCAS
        if payload.horse_creator == payload.horse_opponent:
            raise HTTPException(status_code=400, detail="Los caballos deben ser distintos.")

    # 2. Validar existencia de la carrera y disponibilidad de ejemplares
    entries = (
        db.query(RaceEntry)
        .filter(RaceEntry.race_number == payload.race_number)
        .order_by(RaceEntry.horse_number)
        .all()
    )
    if not entries:
        raise HTTPException(status_code=400, detail="Esa carrera no existe en la cartelera.")

    horses = {e.horse_number: e for e in entries}
    if payload.horse_creator not in horses:
        raise HTTPException(status_code=400, detail="El caballo elegido no corre en esa carrera.")
    if payload.horse_opponent not in horses:
        raise HTTPException(status_code=400, detail="El caballo rival no corre en esa carrera.")

    if is_morocha:
        if payload.horse_creator_2 not in horses:
            raise HTTPException(status_code=400, detail="El segundo caballo propio no corre en esa carrera.")
        if payload.horse_opponent_2 not in horses:
            raise HTTPException(status_code=400, detail="El segundo caballo rival no corre en esa carrera.")

    # 3. Validar stake y saldo disponible (Escrow)
    stake = round(float(payload.stake), 2)
    if stake <= 0:
        raise HTTPException(status_code=400, detail="El stake debe ser mayor que cero.")
    if (user.balance or 0.0) < stake:
        raise HTTPException(status_code=409, detail="Balance insuficiente para retener en escrow.")

    # Retención de saldo en escrow
    user.balance = round((user.balance or 0.0) - stake, 2)

    race_datetime = min(e.race_datetime for e in entries)

    # 4. Instanciación y guardado del duelo
    duel = Duel(
        duel_type_id=duel_type.id,
        race_number=payload.race_number,
        race_datetime=race_datetime,
        horse_creator=payload.horse_creator,
        horse_opponent=payload.horse_opponent,
        horse_creator_name=horses[payload.horse_creator].horse_name,
        horse_opponent_name=horses[payload.horse_opponent].horse_name,
        horse_creator_2=payload.horse_creator_2 if is_morocha else None,
        horse_opponent_2=payload.horse_opponent_2 if is_morocha else None,
        horse_creator_2_name=horses[payload.horse_creator_2].horse_name if is_morocha and payload.horse_creator_2 in horses else None,
        horse_opponent_2_name=horses[payload.horse_opponent_2].horse_name if is_morocha and payload.horse_opponent_2 in horses else None,
        horse_acceptor=None,
        stake=stake,
        fee_percentage=FEE_PERCENTAGE,
        status=DUEL_OPEN,
        creator_id=user.id,
    )

    db.add(duel)
    db.commit()
    db.refresh(duel)
    return _serialize(duel, db)
# ────────────────────────────── Aceptar duelo ──────────────────────────────
@router.post("/duels/{duel_id}/accept")
def accept_duel(
    duel_id: int,
    payload: Optional[DuelAccept] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Acepta un duelo OPEN igualando el stake (también retenido en escrow).
    El oponente queda fijado al caballo rival propuesto por el creador.
    """
    duel = db.get(Duel, duel_id)
    if duel is None:
        raise HTTPException(status_code=404, detail="Duelo no encontrado.")
    if duel.status != DUEL_OPEN:
        raise HTTPException(status_code=409, detail="El duelo ya no está disponible.")
    if duel.creator_id == user.id:
        raise HTTPException(status_code=400, detail="No puedes aceptar tu propio duelo.")
    if payload is not None and payload.horse_acceptor is not None:
        if payload.horse_acceptor != duel.horse_opponent:
            raise HTTPException(
                status_code=400,
                detail="Debes tomar el caballo rival propuesto en el duelo.",
            )
    if (user.balance or 0.0) < duel.stake:
        raise HTTPException(status_code=409, detail="Balance insuficiente para igualar el stake.")

    user.balance = round((user.balance or 0.0) - duel.stake, 2)
    duel.acceptor_id = user.id
    duel.horse_acceptor = duel.horse_opponent
    duel.status = DUEL_ACTIVE
    duel.accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(duel)
    return _serialize(duel, db)


# ─────────────────────── Cancelar duelo (solo OPEN) ───────────────────────
@router.post("/duels/{duel_id}/cancel")
def cancel_duel(
    duel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cancela un duelo aún NO aceptado: reembolsa el escrow al creador y
    elimina el registro (el catálogo de estados permanece OPEN/ACTIVE/RESOLVED).
    Solo puede el creador o el administrador.
    """
    duel = db.get(Duel, duel_id)
    if duel is None:
        raise HTTPException(status_code=404, detail="Duelo no encontrado.")
    if duel.status != DUEL_OPEN:
        raise HTTPException(status_code=409, detail="Solo se pueden cancelar duelos abiertos.")
    if duel.creator_id != user.id and user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Solo el creador puede cancelar este duelo.")

    creator = db.get(User, duel.creator_id)
    if creator is not None:
        creator.balance = round((creator.balance or 0.0) + duel.stake, 2)
    db.delete(duel)
    db.commit()
    return {"detail": "Duelo cancelado y stake reembolsado.", "id": duel_id}


# ─────────────────────── Resolución (únicamente admin) ───────────────────────
@router.get("/admin/duels")
def admin_duels(
    status: Optional[str] = Query(default=None, description="OPEN | ACTIVE | RESOLVED"),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Listado administrativo de duelos (para el módulo Resolver y auditoría)."""
    query = db.query(Duel)
    if status:
        query = query.filter(Duel.status == status.upper())
    duels = query.order_by(Duel.created_at.desc()).all()
    return [_serialize(d, db) for d in duels]


# ───────────────── Motor de resolución (helpers reutilizables) ─────────────────
def _resolve_refund(db: Session, duel: Duel, note: str) -> dict:
    """Reembolsa el escrow completo a ambos participantes (sin comisión)."""
    creator = db.get(User, duel.creator_id)
    acceptor = db.get(User, duel.acceptor_id) if duel.acceptor_id else None
    if creator is not None:
        creator.balance = round((creator.balance or 0.0) + duel.stake, 2)
    if acceptor is not None:
        acceptor.balance = round((acceptor.balance or 0.0) + duel.stake, 2)

    duel.status = DUEL_RESOLVED
    duel.winner_id = None
    duel.winner_horse_number = None
    duel.commission_amount = 0.0
    duel.payout_amount = 0.0
    duel.resolution_note = note
    duel.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(duel)

    data = _serialize(duel, db)
    data.update({"pot": round(duel.stake * 2, 2), "commission": 0.0, "payout": 0.0, "refund": True})
    return data


def _resolve_payout(db: Session, duel: Duel, winner_horse: int, note: str) -> dict:
    """Abona el 95 % del pozo al ganador y retiene el 5 % de comisión (la casa)."""
    winner_user_id = duel.creator_id if winner_horse == duel.horse_creator else duel.acceptor_id
    if winner_user_id is None:
        raise HTTPException(status_code=409, detail="El duelo no tiene oponente registrado.")

    fee_percentage = duel.fee_percentage if duel.fee_percentage is not None else FEE_PERCENTAGE
    pot = round((duel.stake or 0.0) * 2, 2)
    commission = round(pot * fee_percentage, 2)
    payout = round(pot - commission, 2)

    winner_user = db.get(User, winner_user_id)
    if winner_user is None:
        raise HTTPException(status_code=404, detail="Usuario ganador no encontrado.")
    winner_user.balance = round((winner_user.balance or 0.0) + payout, 2)

    duel.status = DUEL_RESOLVED
    duel.winner_id = winner_user_id
    duel.winner_horse_number = winner_horse
    duel.commission_amount = commission
    duel.payout_amount = payout
    duel.resolution_note = note
    duel.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(duel)

    data = _serialize(duel, db)
    data.update(
        {
            "pot": pot,
            "commission": commission,
            "commission_percentage": fee_percentage,
            "payout": payout,
        }
    )
    return data


def resolve_duel_core(
    db: Session,
    duel: Duel,
    requested: Optional[int] = None,
    note: Optional[str] = None,
) -> dict:
    """
    Lógica de resolución (reutilizable): valida el estado, aplica la regla del
    tipo de duelo y, si la carrera tiene marcador oficial (1° al 5°), lo usa o
    valida frente a la selección del administrador.

    Regla del marcador: un caballo fuera del top 5 está "fuera del marcador"
    (perdedor); si ambos quedan fuera → reembolso total sin comisión.
    """
    if duel.status != DUEL_ACTIVE:
        raise HTTPException(
            status_code=409,
            detail="Solo se pueden resolver duelos ACTIVOS (aceptados por un oponente).",
        )

    duel_type = db.get(DuelType, duel.duel_type_id)
    rule = (duel_type.logic_rule if duel_type else "MANUAL").strip().upper()
    horses = (duel.horse_creator, duel.horse_opponent)
    positions = get_official_positions(db, duel.race_number)  # {} si no hay marcador

    # ── Empate declarado → reembolso total, sin comisión ──
    if rule == RULE_TIE:
        return _resolve_refund(
            db, duel, note or "Empate: reembolso total del escrow a ambos participantes."
        )

    # ── Regla de marcador oficial: requiere posiciones 1°-5° ──
    if rule == RULE_OFFICIAL:
        if not positions:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"La carrera {duel.race_number} no tiene posiciones oficiales (1° al 5°). "
                    "Regístralas en «Resultados oficiales» antes de resolver."
                ),
            )
        winner_horse, outcome_note = official_outcome(
            positions, duel.horse_creator, duel.horse_opponent
        )
        if winner_horse is None:
            return _resolve_refund(db, duel, outcome_note)
        if requested is not None and requested != winner_horse:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El marcador oficial indica que gana el caballo N.º {winner_horse}; "
                    f"no coincide con el indicado (N.º {requested})."
                ),
            )
        return _resolve_payout(db, duel, winner_horse, note or outcome_note)

    # Las reglas numéricas (LOWEST/HIGHEST) son sintéticas: no usan el marcador.
    # ── Reglas deterministas numéricas ──
    if rule == RULE_LOWEST:
        winner_horse = min(horses)
    elif rule == RULE_HIGHEST:
        winner_horse = max(horses)
    else:
        # MANUAL y reglas personalizadas no interpretadas por el motor.
        if positions:
            # El marcador oficial manda: se valida la selección del admin.
            official_winner, outcome_note = official_outcome(
                positions, duel.horse_creator, duel.horse_opponent
            )
            if official_winner is None:
                # Ninguno clasificó en el top 5 → ambos "perdedores": reembolso.
                return _resolve_refund(db, duel, outcome_note)
            if requested is not None and requested != official_winner:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"El marcador oficial indica que gana el caballo N.º {official_winner} "
                        f"— {outcome_note} Tu selección (N.º {requested}) no coincide."
                    ),
                )
            winner_horse = official_winner
            note = note or outcome_note
        else:
            if requested is None:
                raise HTTPException(
                    status_code=400,
                    detail="Esta regla requiere indicar winner_horse_number (caballo ganador oficial).",
                )
            winner_horse = requested

    if winner_horse not in horses:
        raise HTTPException(
            status_code=400,
            detail="El caballo ganador debe ser uno de los dos en pugna en este duelo.",
        )
    if rule in (RULE_LOWEST, RULE_HIGHEST) and requested is not None and requested != winner_horse:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La regla {rule} determina que gana el caballo N.º {winner_horse}; "
                f"no coincide con el indicado (N.º {requested})."
            ),
        )

    return _resolve_payout(db, duel, winner_horse, note or f"Regla aplicada: {rule}.")


@router.post("/admin/duels/{duel_id}/resolve")
def resolve_duel(
    duel_id: int,
    payload: Optional[ResolveDuel] = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    Resuelve un duelo ACTIVO aplicando la regla lógica de su tipo de duelo —
    usando o validando el marcador oficial (1° al 5°) cuando la carrera lo
    tenga —: calcula el pozo (stake x 2), retiene el 5 % de comisión para la
    casa y abona el 95 % restante al ganador.
    """
    duel = db.get(Duel, duel_id)
    if duel is None:
        raise HTTPException(status_code=404, detail="Duelo no encontrado.")
    requested = payload.winner_horse_number if payload else None
    note = payload.note.strip() if payload and payload.note else None
    return resolve_duel_core(db, duel, requested, note)
